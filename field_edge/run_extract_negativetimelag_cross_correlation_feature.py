r"""
compute the time lagged cross correlation coefficient between the citation count time series of the citing paper and the cited paper
leave the maximal correlation within a time lagged parameter range [-L, 0). By default L = 3
parameters: <citation_link_table_name> <citation_timeseries_table_name> (<max_timelag> <feature_name>)
==================

"""

from ast import Num
import os
import re
import string
import json
import sys
import numpy
import scipy
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

# import MySQLdb
import odbcdb
from odbcdb import *
from scipy.stats import mannwhitneyu
from scipy.stats import ttest_ind

# the overlapping years should be at least MIN_YEAR_SPAN
MIN_YEAR_SPAN = 5

# for each citation time series, will truncate the ending curve if it drops below MIN_CITATION_PERCENT * max(series) for MAX_MIN_CITATION_YEAR years
MIN_CITATION_PERCENT = 0.1
MAX_MIN_CITATION_YEAR = 5

# the average citation per year should be at least MIN_AVG_CITATION_PER_YEAR in the compared sub-time-series
MIN_AVG_CITATION_PER_YEAR = 2
MIN_TOTAL_CITATION = 5


def average(vector):
    return sum(vector) / float(len(vector))


def average_abs(vector):
    return sum(numpy.absolute(vector)) / float(len(vector))


def computeTruncatedNum(citation_count_timeseries):

    minCountThre = max(citation_count_timeseries) * MIN_CITATION_PERCENT
    maxCount = max(citation_count_timeseries)

    maxCountIndex = 0
    for i in range(len(citation_count_timeseries)):
        if citation_count_timeseries[i] == maxCount:
            maxCountIndex = i
            break

    belowThreCount = 0
    truncateIndex = len(citation_count_timeseries) - 1
    for i in range(maxCountIndex, len(citation_count_timeseries)):
        if citation_count_timeseries[i] < minCountThre:
            belowThreCount = belowThreCount + 1
        else:
            belowThreCount = 0

        if belowThreCount >= MAX_MIN_CITATION_YEAR:
            truncateIndex = i
            break

    return len(citation_count_timeseries) - 1 - truncateIndex


def computeMaxTimeLaggedCrossCorrelation(citingRow, citedRow, maxTimeLag):


    citing_totalCitationCount = int(citingRow[2])
    cited_totalCitationCount = int(citedRow[2])
    if (
        citing_totalCitationCount < MIN_TOTAL_CITATION
        or cited_totalCitationCount < MIN_TOTAL_CITATION
    ):
        return None, None

    citing_citeStartYear = int(citingRow[0])
    citing_citeEndYear = int(citingRow[1])
    citing_citationCountByYear = list(map(int, str(citingRow[3]).strip().split(",")))

    cited_citeStartYear = int(citedRow[0])
    cited_citeEndYear = int(citedRow[1])
    cited_citationCountByYear = list(map(int, str(citedRow[3]).strip().split(",")))

    if (
        (citing_citeStartYear < cited_citeStartYear)
        or (citing_citeStartYear <= 1900)
        or (cited_citeStartYear <= 1900)
    ):
        print(
            "warning: illegal overlapped citation time series! ID: ",
            str(citing_citeStartYear),
            ",",
            str(cited_citeStartYear),
        )
        return None, None

    citingTruncated = computeTruncatedNum(citing_citationCountByYear)
    citedTruncated = computeTruncatedNum(cited_citationCountByYear)

    if citingTruncated > 0:
        citing_citeEndYear = citing_citeEndYear - citingTruncated
        citing_citationCountByYear = citing_citationCountByYear[0:-citingTruncated]

    if citedTruncated > 0:
        cited_citeEndYear = cited_citeEndYear - citedTruncated
        cited_citationCountByYear = cited_citationCountByYear[0:-citedTruncated]

    bestTimeLag = None
    maxCorrelation = 0

    for timeLag in range(-maxTimeLag, 0):

        correlation = computeCrossCorrelation(
            citing_citeStartYear + timeLag,
            citing_citeEndYear + timeLag,
            cited_citeStartYear,
            cited_citeEndYear,
            citing_citationCountByYear,
            cited_citationCountByYear,
        )

        if correlation != None and abs(correlation) >= abs(maxCorrelation):
            maxCorrelation = correlation
            bestTimeLag = timeLag

    if bestTimeLag != None:
        return bestTimeLag, maxCorrelation
    else:
        return None, None


def computeCrossCorrelation(
    citing_citeStartYear,
    citing_citeEndYear,
    cited_citeStartYear,
    cited_citeEndYear,
    citing_citationCountByYear,
    cited_citationCountByYear,
):
    start_year = max(citing_citeStartYear, cited_citeStartYear)
    end_year = min(citing_citeEndYear, cited_citeEndYear)
    length_timeseries = end_year - start_year + 1

    # the overlapping years should be at least MIN_YEAR_SPAN
    if length_timeseries < MIN_YEAR_SPAN:
        return None

    citing_timeseries = citing_citationCountByYear[
        start_year
        - citing_citeStartYear : start_year
        - citing_citeStartYear
        + length_timeseries
    ]
    cited_timeseries = cited_citationCountByYear[
        start_year
        - cited_citeStartYear : start_year
        - cited_citeStartYear
        + length_timeseries
    ]

    # the average citation per year should be at least MIN_AVG_CITATION_PER_YEAR in the compared sub-time-series

    if (average(citing_timeseries) < MIN_AVG_CITATION_PER_YEAR) or (
        average(cited_timeseries) < MIN_AVG_CITATION_PER_YEAR
    ):
        return None

    # print(citing_timeseries, cited_timeseries)

    return numpy.corrcoef(citing_timeseries, cited_timeseries)[0, 1]


host = "127.0.0.1"
port = "3306"
usr = "root"
pwd = "Vis_2014"

TABLE_NAME = "$$TABLE_NAME$$"
COLUMN_NAME = "$$COLUMN_NAME$$"

selectInheritanceLink = "select citingpaperID, citedpaperID from $$TABLE_NAME$$"

selectGroupOneFeature = "select $$COLUMN_NAME$$ from $$TABLE_NAME$$ where inheritance > 0 and not isnull($$COLUMN_NAME$$);"
selectGroupTwoFeature = "select $$COLUMN_NAME$$ from $$TABLE_NAME$$ where inheritance <= 0 and not isnull($$COLUMN_NAME$$);"

if len(sys.argv) < 4:
    print("Not enough parameters: ", len(sys.argv))
    sys.exit

citation_link_table_name = sys.argv[1]
database = sys.argv[2]
citation_timeseries_table_name = sys.argv[3]

engine = create_engine('mysql+pymysql://root:Vis_2014@localhost:3306/'+database)
sql = '''select citeStartYear, citeEndYear, totalCitationCount, citationCountByYear, paperID from $$TABLE_NAME$$;'''

maxTimeLag = 5
feature_name = "negativetimelagged_cross_correlation_feature"

if len(sys.argv) > 4:
    maxTimeLag = int(sys.argv[4])

if len(sys.argv) > 5:
    feature_name = sys.argv[5]

selectInheritanceLink = selectInheritanceLink.replace(
    TABLE_NAME, citation_link_table_name
)

sql = sql.replace(TABLE_NAME, citation_timeseries_table_name)
db = pd.read_sql_query(sql, engine)

# conn = MySQLdb.Connection(user=usr, passwd=pwd, db=database, host=host, port=int(port))
conn = ConnectMySQLDB(host, port, database, usr, pwd)
db_cursor = conn.cursor()

# add the feature column if non-existing

db_cursor.execute(selectInheritanceLink)
rows = db_cursor.fetchall()
citingpaperID_list=[]
citedpaperID_list=[]
feature_name_list=[]
for index in range(len(rows)):
    row = rows[index]
    citingpaperID = str(row[0])
    citedpaperID = str(row[1])
    citingpaperID_list.append(citingpaperID)
    citedpaperID_list.append(citedpaperID)

    citingRow = db.loc[db['paperID']==citingpaperID].values.tolist()
    
    if len(citingRow) == 0:
        feature_name_list.append(np.nan)
        # print("citing is none: ", str(citingpaperID))
        continue
    
    citedRow = db.loc[db['paperID']==citedpaperID].values.tolist()

    if len(citedRow) == 0:
        feature_name_list.append(np.nan)
        # print("cited is none: ", str(citedpaperID))
        continue

    time_lag, cross_correlation_feature = computeMaxTimeLaggedCrossCorrelation(
        citingRow[0], citedRow[0], maxTimeLag
    )

    # if cross_correlation_feature != None:
    #     cross_correlation_feature = str(time_lag) + ":" + str(cross_correlation_feature)
    feature_name_list.append(cross_correlation_feature)
    
    if index % 100 == 0:
        print("Compute features for ", str(index), " features!")

print(len(feature_name_list),len(rows),len(citingpaperID_list),len(citedpaperID_list))

df_feature = pd.DataFrame({"negativetimelagged_cross_correlation_feature": feature_name_list})
df_csv=pd.read_csv("features.csv")
df_feature=pd.concat([df_csv, df_feature], axis=1)
df_feature.to_csv('features.csv',index=False)

db_cursor.close()
conn.close()
