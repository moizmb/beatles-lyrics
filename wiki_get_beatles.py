# -*- coding: utf-8 -*-
# This file cleans the beatles songs information
# from the wikipedia page below and cleans the names
# and provides an alias for album names.(i.e. UK and
# US versions of albums are named differently. The US
# version becomes the alias)

import re
import os
import json
import csv
import string

import requests

from bs4 import BeautifulSoup
import pandas as pd

def parse_table(table, header=True):
    """
    :params table: bs4.element.tag, Table that has to be parsed
    :params header: Boolean, Indicates if header needs to be parsed
    :returns table_list: list, list of rows parsed as list
    """
    table_list = []
    rows = table.findAll("tr")

    def parse_row(row):
        row_cells = row.findChildren(["th", "td"])
        row_list = [c.get_text() for c in row_cells]

        return [r.strip(' ”"') for r in row_list]

    if header:
        header_row = parse_row(rows[0])
        table_list.append(header_row)
        rows = rows[1:]

    for row in rows:
        table_list.append(parse_row(row))

    return table_list


def songwriters(cell):
    """
    :params cell: String with newline separated artists.
                  Artists are sometimes included in brackets
                  as (with xyz)
    :returns songwriters: List object of songwriters
    """

    songwriters = cell.split("\n")
    songwriters_parsed = []

    for writer in songwriters:
        flag = 1

        # Names have refs ahead of them in the form Lennon[1]
        ref = re.search(r"(.+)\[[0-9]+\]", cell)
        if ref:
            writer = ref.groups()[0]

        # Searches for (with xy and za)
        with_more = re.search(r"\(with (.+) and (.+)\)", writer)
        if flag and with_more:
            groups = with_more.groups()
            songwriters_parsed.extend(groups)
            flag = 0

        # Writers in the form xy and wr
        more_than_one = re.search(r"(.+) and (.+)", writer)
        if flag and more_than_one:
            groups = more_than_one.groups()
            songwriters_parsed.extend(groups)
            flag = 0

        # Writers in the form xs, as and fg
        comma_and = re.search(r"(.+), (.+) and (.+)", writer)
        if flag and comma_and:
            groups = comma_and.groups()
            songwriters_parsed.extend(groups)
            flag = 0

        # Searches for (with xy and za)
        starts_with_and = re.search(r"and (.+)", writer)
        if flag and starts_with_and:
            groups = starts_with_and.groups()
            songwriters_parsed.append(groups[0])
            flag = 0

        # Searches for (with xy)
        with_single = re.search(r"\(with (.+)\)", writer)
        if flag and with_single:
            groups = with_single.groups()
            songwriters_parsed.append(groups[0])
            flag = 0

        # Dash separated names
        dash_separated = re.search(r'(.+)–(.+)( .+|)', writer)
        if flag and dash_separated:
            groups = dash_separated.groups()
            songwriters_parsed.append(groups[0])
            flag = 0

        # Ringo Starr is sometimes credited as starkey
        starkey = re.search(r"Starkey.+", writer)
        if flag and starkey:
            songwriters_parsed.append("Starr")
            flag = 0

        # Comma separated names
        if len(writer.split(",")) > 1:
            writer = list(map(lambda x: x.strip(), writer.split(",")))
            songwriters_parsed.extend(writer)
            flag = 0

        if flag:
            songwriters_parsed.append(writer)

        not_needed_artists = ["", "and Roll”)", "Roll”)", "Traditional"]

    return [x for x in songwriters_parsed if x not in not_needed_artists]


writer_aliases = {
    "McCartney": "Paul McCartney",
    "Lennon": "John Lennon",
    "Starr": "Ringo Starr",
    "Harrison": "George Harrison",
    "Mike Stoller/Little Richard": "Mike Stoller",
    "Robert \"Bumps\" Blackwell": "Robert Blackwell",
    "arr. Lennon": "John Lennon",
    "Charles Calhoun(“Shake": "Charles Calhoun",
    "John Marascalco (\"Rip It Up”)": "John Marascalco",
    "Ono": "Yoko Ono",
    "McCartney (as Bernard Webb)": "McCartney",
    'McCartney ("Step Inside Love”)': "McCartney",
    'Carl Perkins ("Blue Suede Shoes")': 'Carl Perkins'
}


def aliases(names, aliases):
    """
    :params name: List of strings whose alias must be found
    :params aliases: Dict of alias names
    :returns alias: Alias for name based on aliases mapping
    """
    names_copy = names[:]
    for i in range(len(names)):
        name = names[i]
        value = aliases.get(name, None)
        if value is not None:
            names_copy[i] = value

    return names_copy


def _lowercase(obj):
    """ Make dictionary lowercase """
    if isinstance(obj, dict):
        return {k.lower():_lowercase(v) for k, v in obj.items()}
    elif isinstance(obj, (list, set, tuple)):
        t = type(obj)
        return t(_lowercase(o) for o in obj)
    elif isinstance(obj, str):
        return obj.lower()
    else:
        return obj



def find_dict(lst, key, value):
    """
    :params lst: List of iterables
    :params key: Key according to which the iterable has to be found
    :params value: Value that must be found in the key
    :returns index: Index at which key, value pair was found
    """
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i
    return None


def map_lyrics(song_name, lyrics):
    """
    :params song_name: Song name that needs to be mapped
    :params lyrics: json object of lyrics
    :returns lyrics: Lyrics mapped by the song_name
    """

    song_name = song_name.lower()
    idx = find_dict(lyrics, "song", song_name)

    lyric = lyrics[idx]["lyrics"] if idx else None
    return lyric


def name_clean(cell):
    # Clean song names
    # Some songs names are repeated twice in the name
    # RegExp captures xy !"(xy)
    name_clean_regex = r".+ !\"(.+)"
    name_reg = re.search(name_clean_regex, cell)
    # Clean name
    if name_reg is not None:
        groups = name_reg.groups()
        song_name = groups[0]
    else:
        song_name = cell

    return song_name.strip() if song_name else song_name


def album_clean(cell):
    """Keeps only UK version of album name"""

    # Regexp captures UK: xy\nUS: xy or UK: xy
    album_clean_regex = r"UK: (.+)\nUS: .+|UK: (.+)"
    album_reg = re.search(album_clean_regex, cell)

    # Clean album name
    # One cell contains only the UK album name
    # Hence the else in the nested if
    if album_reg is not None:
        groups = album_reg.groups()
        album_name = groups[0]
    else:
        album_name = cell

    return album_name.strip() if album_name else album_name


def main():

    # Create data directory if not present
    directory = "./data/"
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Table source is taken from here but page is saved
    # to system just in case it changes in the future
    url = "https://en.wikipedia.org/wiki/List_of_songs_recorded_by_the_Beatles"

    page = requests.get(url)
    soup = BeautifulSoup(page.content.decode("utf-8", "ignore"), "lxml")

    # soup = BeautifulSoup(open("./webpages/beatles-discography.html").read(), "lxml")

    print("Scraping songs table")
    song_table = soup.findAll("table",
                              {"class": [
                                  "wikitable",
                                  "sortable",
                                  "plainrowheaders",
                                  "jquery-tablesorter"]})[1]


    songs_table_parsed = parse_table(song_table)

    file_name = "./data/songs.csv"

    # Save intermediary CSV for further processing
    # print("Saving to {}".format(file_name))
    header_row = ["title", "album", "songwriters", "vocals", "year", "notes", "refs"]
    songs_table_parsed[0] = header_row
    with open(file_name, "w") as f:
        csv_writer = csv.writer(f)
        for row in songs_table_parsed:
            csv_writer.writerow(row)

    # Load songs
    songs = pd.read_csv(file_name)

    # Clean Song names
    songs["title"] = songs["title"].apply(name_clean)

    # Clean Album names
    songs["album"] = songs["album"].fillna("")
    songs["album"] = songs["album"].apply(album_clean)
    songs.loc[songs.album == "1967–1970", "album"] = "1967-1970"

    # Create a songwriters object from the string of songwriters
    songs["songwriters_parsed"] = songs.songwriters.apply(songwriters).apply(aliases, args=(writer_aliases,))

    # Delete unnecessary references column
    del songs["refs"]

    # Typo in album names causes it to show as duplicate record
    songs.loc[songs.album == "Let It Be film", "album"] = "Let it Be film"

    # Year missing in one song
    songs.loc[songs.year.isna(), "year"] = 1963

    # Convert year to type int
    songs["year"] = songs["year"].astype("int")

    # Lower song names to match with lkyric song names
    songs["song_lowered"] = songs["title"].apply(lambda x: x.lower())

    # Load lyrics
    lyrics_file = "./data/lyrics-lyricsfreak.json"
    try:
        lyrics = pd.read_json(lyrics_file)
    except FileNotFoundError:
        raise Exception("{} was not found".format(lyrics_file))

    # Lowercase song names to map with song names from wikipedia
    # Lyrics and song info are from different sources
    # Hence the discrepencies
    lyrics["song_lowered"] = lyrics["song"].apply(lambda x: x.lower())

    # Map lyrics with known songs
    songs["lyrics"] = songs.merge(lyrics[["song_lowered", "lyrics"]], on=["song_lowered"], how="left").lyrics
    songs["notes"] = songs["notes"].fillna("")
    songs["vocals"] = songs["vocals"].fillna("")

    songs["vocals_parsed"] = songs["vocals"].apply(songwriters)

    songs["cover"] = songs["notes"].str.contains("Cover")

    # Save songs and add missing lyrics
    songs.to_csv("./data/songs_cleaned_with_lyrics.csv")


if __name__ == "__main__":
    main()
