import os
import pymysql
import time
from sqlalchemy import create_engine

fieldName = os.environ.get('fieldName', 'visualization')

# 对于 authorID 的限制
authorID_list = ['2147343253', '2076420186', '2122885999', 
                 '2003408012', '2762167099', '2158935544', '3206897746']
# authorID_list = ['3206897746']
# 3206897746    2147343253
ids_string = ', '.join(map(str, authorID_list))
filterCondition = f"authorID IN ({ids_string})"
print(filterCondition)



citation_link_table_name = 'paper_reference_field'
citation_timeseries_table_name = 'papers_field_citation_timeseries'


database = f"scigene_{fieldName}_field"
engine = create_engine(f"mysql+pymysql://root:root@localhost:3306/{database}?charset=utf8")
conn = pymysql.connect(host='localhost',
                            port=3306,
                            user='root',
                            password='root',
                            db=database,
                            charset='utf8')
cursor = conn.cursor()
def execute(sql):
    for _sql in sql.split(';'):
        _sql = _sql.strip()
        if _sql == '':
            continue
        print('executing: ', _sql)
        t = time.time()
        cursor.execute(_sql)
        conn.commit()
        print('[time cost: ', time.time()-t, ']')

def executeFetch(sql):
    sql = sql.strip()
    t = time.time()
    cursor.execute(sql)
    rows = cursor.fetchall()
    print('[time cost: ', time.time()-t, ']')
    return rows