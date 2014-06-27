import logging
from celery.task import task
from celery.schedules import timedelta
from videos.models import VideoUrl, VIDEO_TYPE_YOUTUBE
from videos.types import UPDATE_VERSION_ACTION
from auth.models import CustomUser as User
from models import ThirdPartyAccount
from remover import Remover
from utils.metrics import Gauge


logger = logging.getLogger(__name__)


def get_youtube_data(user_pk):
    """
    Get data for all videos with completed languages.

    Return a list of 3-tuples like this

        (video, language, version,)

    """
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        logger.error('User with PK %s not found' % user_pk)
        return

    usernames = [a.username for a in user.third_party_accounts.all()]
    urls = VideoUrl.objects.filter(owner_username__in=usernames)
    videos = [url.video for url in urls]

    data = []

    for video in videos:
        languages = video.completed_subtitle_languages()

        for language in languages:
            # mirror_on_third_party should be verifying that
            # we only send public versions
            version = language.get_tip(public=False)
            data.append((video, language, version,))

    return data


@task()
def mirror_existing_youtube_videos(user_pk):
    logger.info('Starting sync of existing youtube videos, pk: %s' % user_pk)
    data = get_youtube_data(user_pk)

    if not data:
        logger.info('No videos/subtitles to upload.')
        return

    for video, language, version in data:
        ThirdPartyAccount.objects.mirror_on_third_party(video, language,
                UPDATE_VERSION_ACTION, version)


@task
def gauge_tpas():
    count = ThirdPartyAccount.objects.filter(type=VIDEO_TYPE_YOUTUBE).count()
    Gauge('youtube.accounts_linked').report(count)

@task
def remove_youtube_descriptions_for_tpa(tpa_pk):
    """
    Remove the amara credit in the descriptions of all youtube videos
    associated with the third party account specified as `tpa_pk`.
    """
    try:
        tpa = ThirdPartyAccount.objects.get(pk=tpa_pk)
    except ThirdPartyAccount.DoesNotExist:
        logger.error('tpa account not found', extra={'tpa_pk': tpa_pk})
        return

    remover = Remover(tpa)
    remover.remove_all()