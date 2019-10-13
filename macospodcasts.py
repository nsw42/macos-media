from collections import namedtuple
import datetime
import pathlib
import sqlite3
import sys


class LibraryNotFoundException(Exception):
    pass

Podcast = namedtuple('Podcast', ('title', 'podcast_id'))

Episode = namedtuple('Episode', ('title', 'publication_date', 'playcount', 'filepath'))


def _convert_pubdate(pubdate):
    """
    Convert a publication date, as stored in the database, into a datetime.date instance
    """
    offset = datetime.datetime(2001, 1, 1).timestamp()
    return datetime.date.fromtimestamp(offset+pubdate)


class PodcastLibrary(object):
    @staticmethod
    def _default_podcast_library_dir():
        path = pathlib.Path.home()
        path = path / 'Library' / 'Group Containers' / '243LU875E5.groups.com.apple.podcasts'
        return path

    @staticmethod
    def _podcast_library_file(library_dir):
        path = pathlib.Path(library_dir) / 'Documents' / 'MTLibrary.sqlite'
        return path

    def __init__(self, library_dir=None):
        if library_dir:
            library_dir = pathlib.Path(library_dir)
        else:
            library_dir = PodcastLibrary._default_podcast_library_dir()
        if not library_dir.is_dir():
            raise LibraryNotFoundException(f"Library directory '{library_dir}' not found")
        self.library_dir = library_dir
        library_file = PodcastLibrary._podcast_library_file(self.library_dir)
        if not library_file.is_file():
            raise LibraryNotFoundException(f"Library file '{library_file}' not found")
        self.db = sqlite3.connect(library_file)

    def available_podcasts(self):
        """
        Return a list of Podcast objects
        """
        cursor = self.db.execute('SELECT ZTITLE, Z_PK FROM ZMTPODCAST')
        podcasts = cursor.fetchall()  # list of tuples
        podcasts = [Podcast(title, podcast_id) for (title, podcast_id) in podcasts]
        return podcasts

    def get_podcast_by_title(self, title):
        """
        Return a Podcast object for the given podcast
        """
        cursor = self.db.execute('SELECT ZTITLE, Z_PK FROM ZMTPODCAST WHERE ZTITLE=?', (title, ))
        podcast = cursor.fetchone()  # tuple
        if not podcast:
            raise KeyError(title)
        return Podcast(*podcast)

    def get_podcast_by_id(self, podcast_id):
        """
        Return a Podcast object for the given id
        """
        cursor = self.db.execute('SELECT ZTITLE, Z_PK FROM ZMTPODCAST WHERE Z_PK=?', (podcast_id, ))
        podcast = cursor.fetchone()  # tuple
        if not podcast:
            raise KeyError(podcast_id)
        return Podcast(*podcast)

    def episode_filepath(self, episode_uuid):
        directory = self.library_dir / 'Library' / 'Cache'
        files = list(directory.glob('%s.*' % episode_uuid))
        if len(files) > 1:
            print(f"WARNING: Multiple files found for episode {episode_uuid}", file=sys.stderr)
        return files[0] if files else None

    def episodes_for_show(self, podcast=None, podcast_title=None, podcast_id=None):
        """
        Given a podcast (as a Podcast instance, a podcasttitle or a podcast id)
        returns a list of Episode objects associated with that show.
        """
        if not podcast:
            if podcast_title:
                podcast = self.get_podcast_by_title(podcast_title)
            elif podcast_id:
                podcast = self.get_podcast_by_id(podcast_id)
        if not podcast:
            raise ValueError("Podcast not found")
        cursor = self.db.execute('SELECT ZTITLE, ZPUBDATE, ZPLAYCOUNT, ZUUID FROM ZMTEPISODE WHERE ZPODCAST=? ORDER BY ZPUBDATE', (podcast.podcast_id, ))
        episodes = cursor.fetchall()  # list of tuples
        episodes = [Episode(title, _convert_pubdate(pubdate), playcount, self.episode_filepath(uuid)) for (title, pubdate, playcount, uuid) in episodes]
        return episodes

