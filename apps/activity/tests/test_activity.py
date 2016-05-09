# Amara, universalsubtitles.org
#
# Copyright (C) 2016 Participatory Culture Foundation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see
# http://www.gnu.org/licenses/agpl-3.0.html.

from django.test import TestCase

from activity.models import ActivityRecord
from utils.factories import *
from utils.test_utils import *
import videos.signals

def clear_activity():
    ActivityRecord.objects.all().delete()

class ActivityCreationTest(TestCase):
    def test_video_added(self):
        video = VideoFactory()
        clear_activity()
        videos.signals.video_added.send(
            sender=video,
            video_url=video.get_primary_videourl_obj())
        record = ActivityRecord.objects.get(type='video-added')
        assert_equals(record.video, video)
        assert_equals(record.user, video.user)
        assert_equals(record.created, video.created)

class ActivityVideoLanguageTest(TestCase):
    def test_initial_video_language(self):
        video = VideoFactory(primary_audio_language_code='en')
        record = ActivityRecord.objects.create_for_video_added(video)
        assert_equal(record.video_language_code, 'en')

    def test_video_language_changed(self):
        video = VideoFactory(primary_audio_language_code='en')
        record = ActivityRecord.objects.create_for_video_added(video)
        video.primary_audio_language_code = 'fr'
        videos.signals.language_changed.send(
            sender=video, old_primary_audio_language_code='en')
        assert_equal(reload_obj(record).video_language_code, 'fr')

class TeamVideoActivityTest(TestCase):
    # These tests test video activity and teams.  Our general system for
    # handling this is:
    #  - When a video moves to a team, we make a copy of it for the team it
    #  left.
    #  - We set the team field on the original record to the new team
    #  - The copy on the old team the copied_from field set
    def check_copies(self, record, current_team, old_teams):
        assert_equal(reload_obj(record).team, current_team)
        qs = ActivityRecord.objects.filter(copied_from=record)
        assert_items_equal([a.team for a in qs], old_teams)

    def test_team_video_activity(self):
        # Test activity on a team video
        team = TeamFactory()
        video = TeamVideoFactory(team=team).video
        clear_activity()
        record = ActivityRecord.objects.create_for_video_added(video)
        self.check_copies(record, team, [])

    def test_add_to_team(self):
        # Test adding a non-team video to a team
        video = VideoFactory()
        clear_activity()
        record = ActivityRecord.objects.create_for_video_added(video)
        team = TeamFactory()
        TeamVideoFactory(team=team, video=video)
        self.check_copies(record, team, [])
        
    def move_to_team(self):
        # same thing if we move from 1 team to another
        video = VideoFactory()
        team_video = TeamVideoFactory(video=video)
        first_team = team_video.team
        clear_activity()
        record = ActivityRecord.objects.create_for_video_added(video)
        second_team = TeamFactory()
        team_video.move_to(second_team)
        self.check_copies(record, second_team, [first_team])

    def test_move_back(self):
        # Test moving a video back to a team it was already in before
        video = VideoFactory()
        team_video = TeamVideoFactory(video=video)
        first_team = team_video.team
        clear_activity()
        record = ActivityRecord.objects.create_for_video_added(video)
        second_team = TeamFactory()
        team_video.move_to(second_team)
        team_video.move_to(first_team)
        self.check_copies(record, first_team, [second_team])

    def test_move_back_to_public(self):
        # Test a team video being deleted, putting the video pack in the
        # public area
        video = VideoFactory()
        team_video = TeamVideoFactory(video=video)
        first_team = team_video.team
        clear_activity()
        record = ActivityRecord.objects.create_for_video_added(video)
        team_video.delete()
        self.check_copies(record, None, [first_team])
