from collections import namedtuple
import datetime
import pathlib
import sqlite3
import sys


class LibraryNotFoundException(Exception):
    pass


Podcast = namedtuple('Podcast', ('title', 'podcast_id'))
Podcast.__doc__ = 'Information about a podcast (a show)'
Podcast.title.__doc__ = 'The title of the podcast show (str)'
Podcast.podcast_id.__doc__ = 'The unique identifier of this podcast id (int)'


Episode = namedtuple('Episode', ('title', 'publication_date', 'playcount', 'filepath', 'uuid', 'podcast'))
Episode.__doc__ = 'Information about a single episode from a podcast'
Episode.title.__doc__ = 'The title of this episode (str)'
Episode.publication_date.__doc__ = 'The date that the episode was released (datetime.date)'
Episode.playcount.__doc__ = 'The number of times the episode has been played (int)'
Episode.filepath.__doc__ = 'The absolute path to the episode file (pathlib.Path)'
Episode.uuid.__doc__ = 'The UUID of this episode (str)'
Episode.podcast.__doc__ = 'The Podcast object to which this episode relates'


def _convert_pubdate(pubdate):
    """
    Convert a publication date, as stored in the database, into a datetime.date instance
    """
    if pubdate:
        offset = datetime.datetime(2001, 1, 1).timestamp()
        return datetime.date.fromtimestamp(offset + pubdate)
    return None


def _convert_datetime_to_pubdate(dt):
    """
    Convert a datetime.date to a publication date, as stored in the database.
    """
    if dt:
        dt = datetime.datetime.combine(dt, datetime.datetime.min.time())
        return dt.timestamp() - datetime.datetime(2001, 1, 1).timestamp()
    return None


def _episode_playcount(playcount, manually_played_date):
    if playcount > 0:
        return playcount
    if manually_played_date:
        return 1
    return playcount


class PodcastCache(object):
    def __init__(self, db):
        self.db = db
        self.cache = {}  # indexed by id

    def get(self, podcast_id):
        podcast = self.cache.get(podcast_id)
        if not podcast:
            cursor = self.db.execute('SELECT ZTITLE FROM ZMTPODCAST WHERE Z_PK=?', (podcast_id, ))
            result = cursor.fetchone()  # tuple
            if not result:
                raise KeyError(podcast_id)
            title, = result
            podcast = Podcast(title, podcast_id)
            self.cache[podcast_id] = podcast
        return podcast


class PodcastLibrary(object):
    """A class to access the library of podcasts on macOS
    """

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
        """The main PodcastLibrary class

        Args:
           library_dir (str or pathlib.Path): The podcast library path.
                                              library_dir / Documents / MTLibrary.sqlite must exist

        """

        library_dir = pathlib.Path(library_dir) if library_dir else PodcastLibrary._default_podcast_library_dir()
        if not library_dir.is_dir():
            raise LibraryNotFoundException(f"Library directory '{library_dir}' not found")
        self.library_dir = library_dir
        library_file = PodcastLibrary._podcast_library_file(self.library_dir)
        if not library_file.is_file():
            raise LibraryNotFoundException(f"Library file '{library_file}' not found")
        self.db = sqlite3.connect(library_file)
        self.podcast_cache = PodcastCache(self.db)

    def available_podcasts(self):
        """
        Return a list of Podcast objects
        """
        cursor = self.db.execute('SELECT Z_PK FROM ZMTPODCAST')
        podcasts = cursor.fetchall()  # list of tuples
        return [self.podcast_cache.get(podcast_id) for podcast_id, in podcasts]

    def get_podcast_by_title(self, title):
        """
        Return a Podcast object for the given podcast
        """
        cursor = self.db.execute('SELECT Z_PK FROM ZMTPODCAST WHERE ZTITLE=?', (title, ))
        result = cursor.fetchone()  # tuple
        if not result:
            raise KeyError(title)
        podcast_id, = result
        return self.podcast_cache.get(podcast_id)

    def get_podcast_by_id(self, podcast_id):
        """
        Return a Podcast object for the given id
        """
        return self.podcast_cache.get(podcast_id)

    def episode_filepath(self, episode_uuid):
        """
        Get the path to the episode file with the given identifier
        """
        directory = self.library_dir / 'Library' / 'Cache'
        files = list(directory.glob('%s.*' % episode_uuid))
        if len(files) > 1:
            print(f"WARNING: Multiple files found for episode {episode_uuid}", file=sys.stderr)
        return files[0] if files else None

    def _episode_from_tuple(self, episode_tuple):
        title, pubdate, playcount, manually_played_date, podcast_id, episode_uuid = episode_tuple
        podcast = self.get_podcast_by_id(podcast_id)
        return Episode(title,
                       _convert_pubdate(pubdate),
                       _episode_playcount(playcount, manually_played_date),
                       self.episode_filepath(episode_uuid),
                       episode_uuid,
                       podcast)

    def episodes_for_show(self,
                          podcast=None, podcast_title=None, podcast_id=None,
                          pubdate_after=None,
                          pubdate_before=None,
                          played=None):
        """
        Given a podcast (as a Podcast instance, a podcast title or a podcast id)
        returns a list of Episode objects associated with that show.

        If pubdate_after is specified, only episodes published on or after the
        given date (datetime.date) will be included.

        If pubdate_before is specified, only episodes published on or before the
        given date (datetime.date) will be included.

        If played==True, only episodes that have been played will be included.
        If played==False, only episodes that have not been played will be included.
        """
        if not podcast:
            if podcast_title:
                podcast = self.get_podcast_by_title(podcast_title)
            elif podcast_id:
                podcast = self.get_podcast_by_id(podcast_id)
        if not podcast:
            raise ValueError("Podcast not found")
        query = 'SELECT ZTITLE, ZPUBDATE, ZPLAYCOUNT, ZLASTUSERMARKEDASPLAYEDDATE, ZPODCAST, ZUUID ' \
                + 'FROM ZMTEPISODE WHERE ZPODCAST=?'
        args = [podcast.podcast_id]
        if pubdate_after:
            query += ' AND ZPUBDATE >= ?'
            args.append(_convert_datetime_to_pubdate(pubdate_after))
        if pubdate_before:
            # if we use <= pubdate_before 2020-01-01, that's <= 2020-01-01 00:00:00
            # so add a day, and test for <
            query += ' AND ZPUBDATE < ?'
            args.append(_convert_datetime_to_pubdate(pubdate_before + datetime.timedelta(days=1)))
        if played is True:
            query += ' AND (ZPLAYCOUNT > 0 OR ZLASTUSERMARKEDASPLAYEDDATE > 0)'
        elif played is False:
            query += ' AND (ZPLAYCOUNT = 0 AND ZLASTUSERMARKEDASPLAYEDDATE IS NULL)'

        query += ' ORDER BY ZPUBDATE'
        cursor = self.db.execute(query, args)
        episodes = cursor.fetchall()  # list of tuples
        episodes = [self._episode_from_tuple(episode_tuple) for episode_tuple in episodes]
        return episodes

    def get_episode_by_uuid(self, episode_uuid):
        """
        Return an Episode for the specified UUID.
        Returns None if the UUID was not found.
        """
        # TODO: It looks like ZASSETURL contains the local path, encoded as file:///blah.mp3
        cursor = self.db.execute('SELECT ZTITLE, ZPUBDATE, ZPLAYCOUNT, ZLASTUSERMARKEDASPLAYEDDATE, ZPODCAST, ZUUID '
                                 + 'FROM ZMTEPISODE WHERE ZUUID=?',
                                 (episode_uuid, ))
        episodes = cursor.fetchall()  # list (of length 0..1) of tuples
        if episodes:
            assert len(episodes) == 1
            return self._episode_from_tuple(episodes[0])
        else:
            return None
