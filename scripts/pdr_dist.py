import sys
import os

if __name__ == "__main__":
    here = sys.path[0]
    sys.path.insert(0, os.path.join(here, '..', '..', 'sol'))

#============================ imports =========================================

import math
import influxdb
import Sol
import matplotlib.pyplot as plt
import numpy

#============================ defines =========================================

MAC_LONG_RANGE      = [ "00-17-0d-00-00-b0-00-aa",
                        "00-17-0d-00-00-b0-00-cc",
                        "00-17-0d-00-00-b0-00-87",
                    ]
MAC_MEDIUM_RANGE    = [ "00-17-0d-00-00-30-60-ef",
                        "00-17-0d-00-00-58-32-36"
                    ]

#============================ main    =========================================

def main():
        sol            = Sol.Sol()
        influxClient   = influxdb.client.InfluxDBClient(
                host            = 'localhost',
                port            = '8086',
                database        = 'realms'
                )

        # get motes ids
        query = "SELECT * FROM SOL_TYPE_DUST_EVENTMOTECREATE \
                WHERE site='ARG_junin'"
        influx_json = influxClient.query(query).raw
        res = sol.influxdb_to_json(influx_json)

        # populate motes list
        motes   = [None]*100
        for m in res:
                motes[m['value']['moteId']] = m
                motes[m['value']['moteId']]['neighbors'] = [None]*100

        # get motes neighbors
        query = "SELECT * FROM SOL_TYPE_DUST_NOTIF_HRNEIGHBORS \
                WHERE site='ARG_junin'"
        influx_json = influxClient.query(query).raw
        res = sol.influxdb_to_json(influx_json)

        # update motes location and populate neighbors list
        for r in res:
            moteId = _getMoteIdFromMac(motes, r['mac'])
            if moteId != -1:
                for n in r['value']['neighbors']:
                    motes[moteId]['neighbors'][n['neighborId']] = n
                    nbrId = n['neighborId']
                    if motes[nbrId] != None:
                        motes[nbrId]['value']['latitude'] = r['value']['latitude']
                        motes[nbrId]['value']['longitude'] = r['value']['longitude']

        # compute distance
        for r in res:
            moteId = _getMoteIdFromMac(motes, r['mac'])
            if moteId != -1:
                for n in r['value']['neighbors']:
                    nbrId = n['neighborId']
                    if motes[nbrId] != None:
                        # compute distance with neighbor
                        dist    = _distance_on_unit_sphere(
                                    float(r['value']['latitude']),
                                    float(r['value']['longitude']),
                                    float(motes[nbrId]['value']['latitude']),
                                    float(motes[nbrId]['value']['longitude'])
                                )
                        motes[moteId]['neighbors'][nbrId]['distance'] = dist

        # write result
        fw = open('pdr_dist.out', 'w')
        for m in motes:
            if m != None:
                for n in m['neighbors']:
                    if n != None and int(n['numTxPackets']) != 0 and 'distance' in n:
                        nbrId = n['neighborId']
                        pdr         = (int(n['numTxPackets'])-int(n['numTxFailures'])
                                        )/float(n['numTxPackets'])*100
                        mote1_type   = 0
                        if m['value']['macAddress'] in MAC_LONG_RANGE:
                            mote1_type = 2
                        if m['value']['macAddress'] in MAC_MEDIUM_RANGE:
                            mote1_type = 1
                        mote2_type   = 0
                        if motes[nbrId]['value']['macAddress'] in MAC_LONG_RANGE:
                            mote2_type = 2
                        if motes[nbrId]['value']['macAddress'] in MAC_MEDIUM_RANGE:
                            mote2_type = 1
                        fw.write(str(m['value']['macAddress']) + \
                                " " + str(motes[nbrId]['value']['macAddress']) + \
                                " " + str(n['distance']) + \
                                " " + str(pdr) +
                                " " + str(mote1_type) +
                                " " + str(mote2_type) + "\n"
                                )
        fw.close()

        # create graph
        plt.figure()
        with open('pdr_dist.out') as f:
            x_series    = [[[],[],[]],[[],[],[]],[[],[],[]]]
            y_series    = [[[],[],[]],[[],[],[]],[[],[],[]]]
            for line in f:
                line_list = line.split(' ')
                mote1_type  = int(line_list[4])
                mote2_type  = int(line_list[5])
                pdr         = float(line_list[2])
                dist        = float(line_list[3])

                x_series[mote1_type][mote2_type].append(pdr)
                y_series[mote1_type][mote2_type].append(dist)
        fw.close()
        plt.xlabel('Distance (m)')
        plt.ylabel('PDR')
        colors = iter(['r', 'b', 'g', 'c', 'm', 'y', 'k', 'w', '0.50'])
        mote_types=['DC9003', 'DC9018', 'LongRange']
        for i in range(0, len(x_series)):
            for j in range(0, len(y_series)):
                plt.plot(x_series[i][j],
                        y_series[i][j],
                        marker='o',
                        linestyle='None',
                        color=next(colors),
                        label=mote_types[i]+' to '+mote_types[j]
                        )
        plt.legend()
        plt.show()

#============================ helpers =========================================

def _getMoteIdFromMac(motes, mac):
        for index, m in enumerate(motes):
                if m != None:
                        if m['value']['macAddress'] == mac:
                                return index
        return -1

def _distance_on_unit_sphere(lat1, long1, lat2, long2):
    # Convert latitude and longitude to
    # spherical coordinates in radians.
    degrees_to_radians = math.pi/180.0

    # phi = 90 - latitude
    phi1 = (90.0 - lat1)*degrees_to_radians
    phi2 = (90.0 - lat2)*degrees_to_radians

    # theta = longitude
    theta1 = long1*degrees_to_radians
    theta2 = long2*degrees_to_radians

    # Compute spherical distance from spherical coordinates.

    # For two locations in spherical coordinates
    # (1, theta, phi) and (1, theta', phi')
    # cosine( arc length ) =
    # sin phi sin phi' cos(theta-theta') + cos phi cos phi'
    # distance = rho * arc length

    cos = (math.sin(phi1)*math.sin(phi2)*math.cos(theta1 - theta2) +
        math.cos(phi1)*math.cos(phi2))
    arc = math.acos( cos )

    # Remember to multiply arc by the radius of the earth
    # in your favorite set of units to get length.
    return arc*6371*1000 # in meters


main()

