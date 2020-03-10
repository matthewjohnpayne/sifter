# -*- coding: utf-8 -*-
# sifter/sifter/precalc.py

'''
    --------------------------------------------------------------
    sifter's precalculation module.

    Jan 2020
    Matt Payne & Mike Alexandersen

    This module provides functionalities to
    (a) create & save new precalculations
    (b) load extant precalculations

    *WRITE MORE STUFF*

    --------------------------------------------------------------
    '''


# Import third-party packages
# --------------------------------------------------------------
import sys
import os
import getpass
import warnings
import numpy as np
from astropy_healpix import HEALPix
from astropy.coordinates import SkyCoord
from astropy import units as u


# Different machines set up differently ...
# ... adding paths to force stuff to work while developing
if getpass.getuser() in ['matthewjohnpayne']:
    #sys.path.append('/Users/matthewjohnpayne/Envs/mpcvenv/obs80/')
    sys.path.append('/Users/matthewjohnpayne/Envs/mpcvenv/')
    
    #from obs80 import parse80
elif False:
    pass
else:
    pass

from mpcpp.obs80.obs80 import parse80
from mpcpp import MPC_library as mpc


# Import neighboring packages
# --------------------------------------------------------------
from . import sql  # New and improved Python3 relative import


# Default for caching stuff using lru_cache
# -------------------------------------------------------------


# Data classes/methods
# -------------------------------------------------------------


class Base():
    '''
        Parent class to hold some file/directory definitions & methods
    '''

    def __init__(self):

        # Filing ...
        #self.HP     = '_healpix.txt'

        # Healpix ...
        self.HP_nside = 16
        self.HP_order = 'nested'
        self.HPix = HEALPix(nside=self.HP_nside, order=self.HP_order)
        self.HP_npix = self.HPix.npix

        # sqlite database specs ...
        self.db_filename = 'sifter.db'

        # MPC Observatory list:
        self.obsCodes = mpc.Observatory()

    def _fetch_data_directory(self, ):
        '''
            Returns the default path to the directory where data will be
            downloaded.

            By default, this method will return ~/.sifter_data/data
            and create this directory if it does not exist.

            If the directory cannot be accessed or created, then it returns
            the local directory (".")

            Returns
            -------
            data_dir : str
            Path to location of `data_dir` where data (FITs files) will be
            downloaded
        '''

        data_dir = os.path.join(os.path.expanduser('~'), '.sifter_data')

        # If it doesn't exist, make a new data directory
        if not os.path.isdir(data_dir):

            try:
                os.mkdir(data_dir)

            # downloads locally if OS error occurs
            except OSError:
                warnings.warn('Warning: unable to create {}. '
                              'Download directory set to be the current '
                              'working directory instead.'.format(data_dir))
            data_dir = '.'

        return data_dir


class Tracklets(Base):
    '''
        Class to facilitate "precalculations" on a list of tracklets
        '''

    def __init__(self, observations=None, verbose=False):

        # Give access to "Base" methods
        super().__init__()

        # connect to db
        self.conn = sql.create_connection(sql.fetch_db_filepath())

        # if observations supplied, process them ...
        if observations is not None:
            self.save_tracklets(self.parse_all_observations(observations,
                                                            verbose))

    def parse_all_observations(self, list_of_observations, verbose=False):
        '''
            read observational input (probably be in obs80-string formats)

            Inputs:
            -------
            list_of_observations :
            - each in obs80 format ???
            - just one massive list. itentify_tracklets will sort it out.

            Returns
            -------
            list of tracklet dictionaries
            - specified as per "parse_tracklet_observations" function
        '''
        return [self.parse_tracklet_observations(tracklet_observations, verbose)
                for tracklet_observations
                in identify_tracklets(list_of_observations)]

    def parse_tracklet_observations(self, observation_list, verbose=False):
        '''
            read observational input (probably be in obs80-string formats)

            Inputs:
            -------
            observation_list : list
            - list of strings containing obs80 lines

            Returns
            -------
            tracklet_dict: dictionary
            - container for all data
            - should be everything needed for subsequent detailed calculations
            - contains:
            - JD: integer; date of first observation
            - HP: integer;  Healpix of first observation
            - JD2: integer; date of last observation
            - HP2: integer; Healpix of last observations
            - RoM: astropy Quantity; Rate of motion (angle per time)
            - AoM: astropy Quantity; Angle of motion, positive,
            measured from East towards North.
            - tracklet_name: string; Unique ID for the tracklet
            - observations: list of strings; the input obs80 lines
            '''
        # Check number of observations given.
        nobs = len(observation_list)
        if nobs == 0:
            raise RuntimeError("Received zero observations. Can't real.")
        if nobs == 1 and verbose:
            print("********** WARNING **********\nReceived 1 observation.")
            print("Will proceed, but RoM and AoM will be 0.\n### WARNING ###")
        elif nobs > 2 and verbose:
            print("Received more than 2 observations.")
            print("Only using first and last one.")
        else:
            pass
        # Parse obs80 lines
        parsed = [obs for obs in parse80(observation_list)]

        # Put everything of use in the tracklet_dictionary
        tracklet_dictionary = {'observations': observation_list}

        # Julian date
        JDfloat = parsed[0].jdutc
        JDfloat2 = parsed[-1].jdutc
        tracklet_dictionary['JD'] = round(JDfloat)
        tracklet_dictionary['JD2'] = round(JDfloat2)

        # Calculate Rate of Motion and Angle of Motion
        Coord = SkyCoord(parsed[0].ra * u.hourangle, parsed[0].dec * u.deg)
        Coord2 = SkyCoord(parsed[-1].ra * u.hourangle, parsed[-1].dec * u.deg)
        Delta_JD = (JDfloat2 - JDfloat) * u.day
        tracklet_dictionary['RoM'] = Coord.separation(Coord2) / Delta_JD
        tracklet_dictionary['AoM'] = Coord.position_angle(Coord2)

        # Find the healpix that the coordinates are in.
        tracklet_dictionary['HP'] = int(self.HPix.lonlat_to_healpix(
                                        Coord.ra, Coord.dec))
        tracklet_dictionary['HP2'] = int(self.HPix.lonlat_to_healpix(
                                         Coord2.ra, Coord2.dec))

        # Create a unique ID for the tracklet. This is done by combining
        # the 5 digit number or 6-7 character temporary designation,
        # the julian date of first obs (up to 14 characters),
        # and the 3 digit observatory code. 26 characters total
        namestr = parsed[0].num if parsed[0].num != '' else parsed[0].desig
        tracklet_name = namestr.ljust(7, '_') + '_'         # name/desig
        tracklet_name += str(JDfloat).ljust(14, '_') + '_'  # JD
        tracklet_name += parsed[0].cod.ljust(3, '_')        # ObsCode
        tracklet_dictionary['tracklet_name'] = tracklet_name

        # We also pre-calculate and save the observatory location
        # for each observation
        observatory_heliocentric_ecliptic_xyz =\
            [self.get_heliocentric_ecliptic_xyz(pi.jdutc, obsCode=pi.cod,
                                                verbose=verbose)
             for pi in parsed]
        tracklet_dictionary['obs_helio-ecliptic_xyz'] =\
            observatory_heliocentric_ecliptic_xyz
        return tracklet_dictionary

    def get_heliocentric_equatorial_xyz(self, jd_utc, obsCode=None,
                                        verbose=False):
        '''
            Get the heliocentric EQUATORIAL vector coordinates of the
            observatory at the time jd_utc.
        '''
        obsCode = check_obsCode(obsCode, verbose)
        return self.obsCodes.getObservatoryPosition(obsCode, jd_utc,
                                                    old=False) * u.au

    def get_heliocentric_ecliptic_xyz(self, jd_utc, obsCode=None,
                                      verbose=False):
        '''
            Get the heliocentric ECLIPTIC vector coordinates of the
            observatory at the time jd_utc.
        '''
        obsCode = check_obsCode(obsCode, verbose)
        helio_OBS_equ = self.get_heliocentric_equatorial_xyz(jd_utc, obsCode)
        helio_OBS_ecl = equatorial_to_ecliptic(helio_OBS_equ)
        return helio_OBS_ecl

    def save_tracklets(self, tracklet_dictionary_list):
        '''
            This should use the results from parse_all_observations
            and store them appropriately in a nice file/database structure.

            Inputs:
            -------
            tracklet_dictionary_list: list-of-dictionaries
            - all data that we want to save for each tracklet

            Returns
            -------

        '''
        JD = [tracklet_dic['JD'] for tracklet_dic in tracklet_dictionary_list]
        HP = [tracklet_dic['HP'] for tracklet_dic in tracklet_dictionary_list]
        tracklet_name = [tracklet_dic['tracklet_name'] for tracklet_dic in tracklet_dictionary_list]

        # upload data (making equal-length lists)
        return sql.upsert_tracklets(self.conn, JD, HP, tracklet_name,
                                    tracklet_dictionary_list)

    def delete_tracklets(self, tracklet_name_list):
        '''
        We need some method to remove tracklets
        '''
        return sql.delete_tracklets(self.conn, tracklet_name_list)


def identify_tracklets(list_of_observations):
    '''
        Read a long list of observational input (probably in
        obs80-string formats) and identifies which lines belong to the
        same tracklet. Returns a list of sub-lists, each containing
        just observations for a single tracklet.

        Inputs:
        -------
        list_of_observations :
        - each in obs80 format ???

        Returns
        -------
        list of list
        - each containing obs80 lines for obs of a single tracklet.
    '''
    # Initiate a list with just the first obs of first tracklet to start with.
    list_of_lists = [[list_of_observations[0]]]
    # Parse all the obs80 lines into a generator
    parsed_all = parse80(list_of_observations)
    # Parse 1st line to check whether following lines belong to same tracklet.
    parsed0 = parsed_all.send(None)
    JD0 = parsed0.jdutc
    namestr0 = parsed0.num if parsed0.num != '' else parsed0.desig
    # Now loop over the rest of the lines, checking whether they belong to
    # the same tracklet as the previous one.
    for obs in list_of_observations[1:]:
        parsed1 = parsed_all.send(None)
        JD1 = parsed1.jdutc
        namestr1 = parsed1.num if parsed1.num != '' else parsed1.desig
        # If next line has same trksub and is within 24 hours, add to tracklet
        if namestr1 == namestr0 and np.abs(JD1 - JD0 <= 1.0):
            list_of_lists[-1].append(obs)
        else:
            list_of_lists.append([obs])
            # Update namestr0 so that next loop checks against current line
            namestr0 = namestr1
        # Update JD0 so that next loop checks against current line
        # Updated outside if, so that tracklet can grow infinitely large,
        # There just has to be no gaps larger than 24 hours.
        JD0 = JD1
    return list_of_lists


def equatorial_to_ecliptic(input_xyz, backwards=False):
    '''
        Convert an cartesian vector from mean equatorial to mean ecliptic.
        backwards=True converts backwards, from ecliptic to equatorial.
        input:
            input_xyz - np.array length 3
            backwards - boolean
        output:
            output_xyz - np.array length 3
    '''
    direction = -1 if backwards else +1
    rotation_matrix = mpc.rotate_matrix(-mpc.Constants.ecl * direction)
    output_xyz = np.dot(rotation_matrix, input_xyz.reshape(-1, 1)).flatten()
    return output_xyz


def check_obsCode(obsCode=None, verbose=False):
    '''
        Check whether a valid Observatory Code has been supplied.
        If None, use 500 (Geocentre).
    '''
    if obsCode is None:
        return '500'
    if obsCode in ['XXX', '']:  # Observations with no ObsCode
        print('Bad ObsCode. Will use geocenter.\n' if verbose else '', end='')
        return '500'				# pretend Geocentre.
    if isinstance(obsCode, int):
        obsCode = str(obsCode)
    if len(obsCode) != 3:
        raise NotImplementedError("Bad Observatory Code!\nObservatory Code "
                                  "must be a three character string!\nFor "
                                  "four character Observatory Codes, please "
                                  "bug M. Alexandersen or M. Payne.")
    return obsCode


# End of file
