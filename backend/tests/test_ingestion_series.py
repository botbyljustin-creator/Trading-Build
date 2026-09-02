"""Verifies playlist-aware channel ingestion never flattens a channel's
distinct series into one undifferentiated video list (ARCHITECTURE.md /
this session's core requirement). Uses a real Postgres database with
`app.ingestion.youtube_client` network calls mocked — skipped with a clear
reason if no database is reachable, matching `test_api_integration.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.core.db import get_engine, get_session_factory
from app.ingestion import youtube_client
from app.ingestion.youtube_client import ChannelPlaylists, PlaylistInfo, VideoMetadata
from app.models.enums import SourceStatus, SourceType
from app.models.project import Project
from app.models.series import Series
from app.models.source import Source, Video
from app.models.user import User
from app.services import ingestion_service


def _database_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _database_available(), reason="Requires a reachable Postgres database."
)


@pytest.fixture
def db():
    session = get_session_factory()()
    yield session
    session.close()


@pytest.fixture
def project(db):
    unique = uuid.uuid4().hex
    user = User(clerk_user_id=f"test-{unique}", email=f"test-{unique}@example.com")
    db.add(user)
    db.flush()
    proj = Project(owner_id=user.id, name="Series Ingestion Test")
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def _fake_metadata(video_id: str, channel_name: str = "Test Creator") -> VideoMetadata:
    return VideoMetadata(
        youtube_video_id=video_id,
        title=f"Video {video_id}",
        channel_name=channel_name,
        channel_id="UC_test",
        publish_date=datetime(2024, 1, 1, tzinfo=UTC),
        duration_seconds=600,
        description="test",
        thumbnail_url=None,
        url=f"https://www.youtube.com/watch?v={video_id}",
    )


def test_channel_with_playlists_creates_one_series_per_playlist(db, project, monkeypatch):
    monkeypatch.setattr(
        youtube_client,
        "list_channel_playlists",
        lambda identifier, max_playlists=25: ChannelPlaylists(
            channel_display_name="Test Creator",
            playlists=[
                PlaylistInfo(playlist_id="PL_2022", title="2022 Mentorship"),
                PlaylistInfo(playlist_id="PL_2023", title="2023 Mentorship"),
            ],
        ),
    )

    def fake_list_playlist_video_ids(playlist_id, max_videos):
        return {"PL_2022": ["vid_2022_a", "vid_2022_b"], "PL_2023": ["vid_2023_a"]}[playlist_id]

    monkeypatch.setattr(youtube_client, "list_playlist_video_ids", fake_list_playlist_video_ids)
    monkeypatch.setattr(youtube_client, "fetch_video_metadata", lambda vid: _fake_metadata(vid))

    source = Source(
        project_id=project.id,
        source_type=SourceType.YOUTUBE_CHANNEL,
        url="https://www.youtube.com/@TestCreator",
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    ingestion_service.resolve_source(db, source)
    db.refresh(source)

    assert source.status == SourceStatus.READY
    series_rows = db.query(Series).filter(Series.project_id == project.id).all()
    assert {s.series_name for s in series_rows} == {"2022 Mentorship", "2023 Mentorship"}
    assert all(s.creator_name == "Test Creator" for s in series_rows)

    videos = db.query(Video).filter(Video.source_id == source.id).all()
    assert len(videos) == 3
    by_series = {}
    for v in videos:
        by_series.setdefault(v.series_id, []).append(v)
    # Each playlist's videos are grouped under exactly one series and keep
    # their playlist-relative position — never mixed with the other series.
    assert len(by_series) == 2
    for series_videos in by_series.values():
        positions = sorted(v.position_in_series for v in series_videos)
        assert positions == list(range(len(series_videos)))

    series_2022 = next(s for s in series_rows if s.series_name == "2022 Mentorship")
    video_ids_2022 = {v.youtube_video_id for v in by_series[series_2022.id]}
    assert video_ids_2022 == {"vid_2022_a", "vid_2022_b"}


def test_channel_without_playlists_falls_back_to_uncategorized_series(db, project, monkeypatch):
    monkeypatch.setattr(
        youtube_client,
        "list_channel_playlists",
        lambda identifier, max_playlists=25: ChannelPlaylists(
            channel_display_name="No Playlists Creator", playlists=[]
        ),
    )
    monkeypatch.setattr(
        youtube_client,
        "list_channel_video_ids",
        lambda identifier, max_videos: ["flat_a", "flat_b"],
    )
    monkeypatch.setattr(
        youtube_client,
        "fetch_video_metadata",
        lambda vid: _fake_metadata(vid, "No Playlists Creator"),
    )

    source = Source(
        project_id=project.id,
        source_type=SourceType.YOUTUBE_CHANNEL,
        url="https://www.youtube.com/@NoPlaylists",
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    ingestion_service.resolve_source(db, source)

    series_rows = db.query(Series).filter(Series.project_id == project.id).all()
    assert len(series_rows) == 1
    assert series_rows[0].series_name == ingestion_service.UNCATEGORIZED_SERIES_NAME
    videos = db.query(Video).filter(Video.source_id == source.id).all()
    assert len(videos) == 2
    assert all(v.series_id == series_rows[0].id for v in videos)


def test_directly_submitted_playlist_creates_single_series_and_backfills_creator(
    db, project, monkeypatch
):
    monkeypatch.setattr(
        youtube_client, "list_playlist_video_ids", lambda playlist_id, max_videos: ["pv_a", "pv_b"]
    )
    monkeypatch.setattr(
        youtube_client, "fetch_video_metadata", lambda vid: _fake_metadata(vid, "Playlist Creator")
    )

    source = Source(
        project_id=project.id,
        source_type=SourceType.YOUTUBE_PLAYLIST,
        url="https://www.youtube.com/playlist?list=PL_solo",
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    ingestion_service.resolve_source(db, source)

    series_rows = db.query(Series).filter(Series.project_id == project.id).all()
    assert len(series_rows) == 1
    assert series_rows[0].youtube_playlist_id == "PL_solo"
    assert series_rows[0].creator_name == "Playlist Creator"
