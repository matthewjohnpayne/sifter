# -*- coding: utf-8 -*-
# sifter/sifter/sql

'''
    --------------------------------------------------------------
    sifter's sqlite module.
    
    Jan 2020
    Matt Payne & Mike Alexandersen
    
    This module provides functionalities to
    ...
    
    *WRITE MORE STUFF*
    
    --------------------------------------------------------------
    '''


# Import third-party packages
# --------------------------------------------------------------
import sys, os
import numpy as np
import sqlite3
from sqlite3 import Error
import pickle

# Import neighboring packages
# --------------------------------------------------------------
from . import precalc  # new better Python3 relative import




# Data classes/methods
#
# N.B. Many of these sqlite functions are copied straight from
# https://www.sqlitetutorial.net/sqlite-python/
# E.g.
# https://www.sqlitetutorial.net/sqlite-python/creating-database/
# https://www.sqlitetutorial.net/sqlite-python/create-tables/
# ...
#
# -------------------------------------------------------------

def fetch_db_filepath():
    '''
    '''
    B = precalc.Base()
    db_dir = B._fetch_data_directory()
    return os.path.join(db_dir , B.db_filename)

def create_connection(db_file):
    """ Create a database connection to the SQLite database
        specified by db_file
        
        inputs:
        -------
        db_file: database file
        
        return: 
        -------
        Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
    
    return conn


def create_table(conn, create_table_sql):
    """ Create a table from the create_table_sql statement
        
        inputs:
        -------
        conn: Connection object
        
        create_table_sql: a CREATE TABLE statement
        
        return:
        -------
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        conn.commit()
    except Error as e:
        print(e)



def create_specific_table(conn):
    """ Create the specific table(s) that we need for *sifter*
        Currently creates:
        (i) tracklets

        inputs:
        -------
        conn: Connection object

        return:
        -------

    """
    
    # Note that I am deliberately setting up the stored *tracklet* data as a "blob"
    # - Because not yet sure what will be in it!
    sql_create_tracklets_table = """ CREATE TABLE IF NOT EXISTS tracklets (
        id integer PRIMARY KEY,
        jd integer NOT NULL,
        hp integer NOT NULL,
        tracklet_name text NOT NULL,
        tracklet blob
        ); """
    
    # create table(s)
    if conn is not None:
        
        # create "jdhp_to_tracklet" table
        create_table(conn, sql_create_tracklets_table)

        # Create compound/combined index on the jd & hp columns
        createSecondaryIndex =  "CREATE INDEX index_jdhp ON tracklets (jd, hp);"
        conn.cursor().execute(createSecondaryIndex)
    
    # remember to commit ...
    conn.commit()




def upsert_tracklet(conn, jd, hp, tracklet_name, tracklet_dict):
    """
        insert/update tracklet data
        
        N.B ...
        https://stackoverflow.com/questions/198692/can-i-pickle-a-python-dictionary-into-a-sqlite3-text-field
        pdata = cPickle.dumps(data, cPickle.HIGHEST_PROTOCOL)
        curr.execute("insert into table (data) values (:data)", sqlite3.Binary(pdata))

        inputs:
        -------
        conn: Connection object
        
        jd : 
        hp : 
        tracklet_name : 
        tracklet_dict :
        
        return:
        -------
        
    """
    
    # Make cursor ...
    cur = conn.cursor()
    
    # Construct sql for tracklet insert ...
    sql =  ''' INSERT OR REPLACE INTO tracklets(jd,hp,tracklet_name,tracklet)
        VALUES(?,?,?,?)
        '''
    
    # Insert
    cur.execute(sql, (jd, hp, tracklet_name, sqlite3.Binary( pickle.dumps(tracklet_dict, pickle.HIGHEST_PROTOCOL) ),))

    # remember to commit ...
    conn.commit()


def upsert_tracklets(conn, jd_list, hp_list, tracklet_name_list, tracklet_dict_list):
    """
        insert/update lists of tracklet data
        
        N.B ...
        https://stackoverflow.com/questions/198692/can-i-pickle-a-python-dictionary-into-a-sqlite3-text-field
        pdata = cPickle.dumps(data, cPickle.HIGHEST_PROTOCOL)
        curr.execute("insert into table (data) values (:data)", sqlite3.Binary(pdata))
        
        inputs:
        -------
        conn: Connection object
        
        jd_list :
        hp_list :
        tracklet_name_list :
        tracklet_dict_list :
        
        return:
        -------
        
        """
    # Make cursor ...
    cur = conn.cursor()

    # construct "records" variable which is apparently ammenable to single insert statement ...
    # https://pythonexamples.org/python-sqlite3-insert-multiple-records-into-table/
    records = [ (int(jd), int(hp), tracklet_name, sqlite3.Binary(pickle.dumps(tracklet_dict, pickle.HIGHEST_PROTOCOL))) \
               for jd, hp, tracklet_name, tracklet_dict \
               in zip(jd_list, hp_list, tracklet_name_list, tracklet_dict_list) ]

    sql = '''INSERT OR REPLACE INTO tracklets(jd,hp,tracklet_name,tracklet) VALUES(?,?,?,?);'''

    # Insert
    cur.executemany(sql, records)

    # remember to commit ...
    conn.commit()




def delete_tracklet(conn, tracklet_name):
    """
        delete tracklet data
        
        inputs:
        -------
        tracklet_name: string
        
        return:
        -------
        
        
    """
    sql = 'DELETE FROM tracklets WHERE tracklet_name=?'
    cur = conn.cursor()
    cur.execute(sql, (tracklet_name,))
    conn.commit()


def delete_tracklets(conn, tracklet_name_list):
    """
        delete list of tracklet data
        
        inputs:
        -------
        tracklet_name: list-of-strings
        
        return:
        -------
        
        
        """
    sql = '''DELETE FROM tracklets WHERE tracklet_name IN (?);'''
    records = [ (tracklet_name,) for tracklet_name in tracklet_name_list ]
    cur = conn.cursor()
    cur.executemany(sql, records)
    conn.commit()



def query_tracklets_jdhp(conn, JD, HP):
    """
       Standard query used to find all tracklets for which jd,hp matches input
       
       inputs:
       -------
       JD: integer
       HP: integer
       
       return:
       -------
       list of tracklet_names

    """
    cur = conn.cursor()
    cur.execute("SELECT tracklet_name, tracklet FROM tracklets WHERE jd=? AND hp=?", ( int(JD), int(HP) , ))
    
    # return a list-of-tuples: (tracklet_name, tracklet_dictionary)
    return [ (row[0] , pickle.loads( row[1] ) ) for row in cur.fetchall() ]


def query_tracklets_jd_hplist(conn, JD, HP_list):
    """
        Standard query used to find all tracklets for which jd,hp_list matches input
        
        inputs:
        -------
        JD: integer
        HP_list: list-of-integers
        
        return:
        -------
        list of tracklet_names
        
        """
    assert isinstance(JD, int) and isinstance(HP_list, list), 'Cannot parse input types in query_tracklets_jd_hplist ... '

    # Get cursor ...
    cur = conn.cursor()

    # Set up query:
    #N.B. https://stackoverflow.com/questions/18363276/how-do-you-do-an-in-query-that-has-multiple-columns-in-sqlite
    for sql in ['''CREATE TEMPORARY TABLE lookup(jd, hp);''',
                '''INSERT OR REPLACE INTO lookup(jd,hp) VALUES(?,?);''',
                '''CREATE INDEX lookup_jd_hp ON lookup(jd, hp);''',
                '''SELECT tracklet_name, tracklet FROM tracklets JOIN lookup ON tracklets.jd = lookup.jd AND tracklets.hp = lookup.hp;''']:
        
        # Execute queries
        print( ' ... = ', sql )
        if 'INSERT' in sql:
            records = [ (JD, hp) for hp in HP_list ]
            cur.executemany(sql, records )
        else:
            cur.execute(sql)

    # return a list-of-tuples: (tracklet_name, tracklet_dictionary)
    return [ (row[0] , pickle.loads( row[1] ) ) for row in cur.fetchall() ]




