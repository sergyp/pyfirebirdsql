#!/usr/bin/env python
##############################################################################
# Copyright (c) 2009-2012 Hajime Nakagami<nakagami@gmail.com>
# All rights reserved.
# Licensed under the New BSD License
# (http://www.freebsd.org/copyright/freebsd-license.html)
#
# Python DB-API 2.0 module for Firebird. 
##############################################################################
import os,sys
sys.path.append('./../')
import firebirdsql
from firebirdsql import *

def debug_print(msg):
    print(msg)

if __name__ == '__main__':
    if sys.platform in ('win32', 'darwin'):
        fbase = os.path.abspath('.') + '/test'
    else:
        import tempfile
        fbase = tempfile.mktemp()
    TEST_HOST = 'localhost'
    TEST_PORT = 3050
    TEST_DATABASE = fbase + '.fdb'
    TEST_DSN = TEST_HOST + '/' + str(TEST_PORT) + ':' + TEST_DATABASE
    print('dsn=', TEST_DSN)
    TEST_USER = 'sysdba'
    TEST_PASS = 'masterkey'
    conn = firebirdsql.create_database(dsn=TEST_DSN,
                        user=TEST_USER, password=TEST_PASS, page_size=2<<13)
    conn.cursor().execute('''
        CREATE TABLE foo (
            a INTEGER NOT NULL,
            b VARCHAR(30) NOT NULL UNIQUE,
            c VARCHAR(1024),
            d DECIMAL(16,3) DEFAULT -0.123,
            e DATE DEFAULT '1967-08-11',
            f TIMESTAMP DEFAULT '1967-08-11 23:45:01',
            g TIME DEFAULT '23:45:01',
            h BLOB SUB_TYPE 1, 
            i DOUBLE PRECISION DEFAULT 0.0,
            j FLOAT DEFAULT 0.0,
            PRIMARY KEY (a),
            CONSTRAINT CHECK_A CHECK (a <> 0)
        )
    ''')
    conn.cursor().execute('''
        CREATE TABLE bar_empty (
            k INTEGER NOT NULL,
            abcdefghijklmnopqrstuvwxyz INTEGER
        )
    ''')
    conn.cursor().execute('''
        CREATE PROCEDURE foo_proc
          RETURNS (out1 INTEGER, out2 VARCHAR(30))
          AS
          BEGIN
            out1 = 1;
            out2 = 'ABC';
          END
    ''')
    conn.cursor().execute('''
        CREATE PROCEDURE bar_proc (param_a INTEGER, param_b VARCHAR(30))
          RETURNS (out1 INTEGER, out2 VARCHAR(30))
          AS
          BEGIN
            out1 = param_a;
            out2 = param_b;
          END
    ''')
    conn.cursor().execute('''
        CREATE PROCEDURE baz_proc(param_a INTEGER)
          RETURNS (out1 INTEGER, out2 VARCHAR(30))
          AS
          BEGIN
            SELECT a, b FROM foo
              WHERE a= :param_a
              INTO :out1, :out2;
            SUSPEND;
          END
    ''')
    conn.commit()

    cur = conn.cursor()
    cur.execute("select * from foo")
    assert cur.fetchone() is None
    cur.close()

    cur = conn.cursor()

    print('foo_proc')
    cur.callproc("foo_proc")
    print(cur.fetchone())
    cur.close()

    cur = conn.cursor()
    try:
        rs = cur.execute("select out1, out2 from foo_proc")
        if rs is None:  # FB1.5
            print('foo_proc not selectable')
        else:
            for r in rs:
                print(r)
    except firebirdsql.OperationalError:    # FB2
        print('foo_proc not selectable')
    finally:
        cur.close()

    print('bar_proc')
    cur = conn.cursor()
    cur.callproc("bar_proc", (1, "ABC"))
    for r in cur.fetchallmap():
        print(r)

    cur.close()

    cur = conn.cursor()
    cur.execute("select a as alias_name from foo")
    assert cur.description[0][0] == 'ALIAS_NAME'
    cur.close()

    # 3 records insert
    conn.cursor().execute("insert into foo(a, b, c,h) values (1, 'a', 'b','This is a memo')")
    conn.cursor().execute("""insert into foo(a, b, c, e, g, i, j) 
        values (2, 'A', 'B', '1999-01-25', '00:00:01', 0.1, 0.1)""")
    conn.cursor().execute("""insert into foo(a, b, c, e, g, i, j) 
        values (3, 'X', 'Y', '2001-07-05', '00:01:02', 0.2, 0.2)""")

    print("select from stored procedure")
    cur = conn.cursor()
    cur.execute("select out1, out2 from baz_proc(?)", (1, ))
    for r in cur.fetchall():
        print(r)
    cur.close()

    # 1 record insert and rollback to savepoint
    cur = conn.cursor()
    conn.savepoint('abcdefghijklmnopqrstuvwxyz')
    cur.execute("""insert into foo(a, b, c, e, g, i, j) 
        values (4, 'x', 'y', '1967-05-08', '00:01:03', 0.3, 0.3)""")
    conn.rollback(savepoint='abcdefghijklmnopqrstuvwxyz')

    conn.cursor().execute("update foo set c='Hajime' where a=1")
    conn.cursor().execute("update foo set c=? where a=2", ('Nakagami', ))
    conn.commit()

    cur = conn.cursor()
    cur.execute("select * from foo where c=?", ('Nakagami', ))
    len(cur.fetchall()) == 1
    cur.close()

    cur = conn.cursor()
    cur.execute("select * from foo")
    assert not cur.fetchone() is None
    assert not cur.fetchone() is None
    assert not cur.fetchone() is None
    assert cur.fetchone() is None
    cur.close()

    cur = conn.cursor()
    cur.execute("select * from foo")
    conn.commit()
    try:
        for r in cur.fetchall():
            print(r)
    except firebirdsql.OperationalError:
        e = sys.exc_info()[1]
        print(e.sql_code)
        assert (e.sql_code == -504          # FB2.1 cursor is not open
            or 335544332 in e.gds_codes)    # FB2.5 invalid transaction handle

    cur = conn.cursor()
    try:
        conn.cursor().execute("insert into foo(a, b, c) values (1, 'a', 'b')")
    except firebirdsql.IntegrityError:
        pass
    try:
        conn.cursor().execute("bad sql")
    except firebirdsql.OperationalError:
        e = sys.exc_info()[1]
        assert e.sql_code == -104

    cur = conn.cursor()
    cur.execute("select * from foo")
    print(cur.description)
    for c in cur.fetchall():
        print(c)

    print('fetchallmap()')
    cur.execute("select * from foo")
    for r in cur.fetchallmap():
        print(r)
        for key in r:
            print (key, r[key])

    print('fetchonemap()')
    cur = conn.cursor()
    cur.execute("select * from foo")
    for k,v in cur.fetchonemap().items():
        print(k, v)

    print('itermap()')
    cur = conn.cursor()
    cur.execute("select * from foo")
    for r in cur.itermap():
        print(r['a'], r['b'], r['c'])

    print('fetchonemap() empty record')
    cur = conn.cursor()
    cur.execute("select * from bar_empty")
    for k,v in cur.fetchonemap().items():
        print(k, v)

    print('cursor iteration')
    cur = conn.cursor()
    cur.execute("select * from foo")
    for (a, b, c, d, e, f, g, h, i, j) in cur:
        print(a, b, c)

    print('long field name from system table')
    cur = conn.cursor()
    cur.execute("select rdb$field_name from rdb$relation_fields where rdb$field_name='ABCDEFGHIJKLMNOPQRSTUVWXYZ'")
    v = cur.fetchone()[0]
    assert v.strip() == 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    conn.close()

    conn = firebirdsql.connect(host=TEST_HOST, database=TEST_DATABASE,
                        port=TEST_PORT, user=TEST_USER, password=TEST_PASS)
    conn.begin()

    print('db_info:')
    requests = [isc_info_ods_version, 
                isc_info_ods_minor_version,
                isc_info_base_level,
                isc_info_db_id,
                isc_info_implementation,
                isc_info_firebird_version,
                isc_info_user_names,
                isc_info_read_idx_count,
                isc_info_creation_date,
    ]
    print(conn.db_info(requests))

    print('trans_info:')
    requests = [isc_info_tra_id, 
                isc_info_tra_oldest_interesting,
                isc_info_tra_oldest_snapshot,
                isc_info_tra_oldest_active,
                isc_info_tra_isolation,
                isc_info_tra_access,
                isc_info_tra_lock_timeout,
    ]
    print(conn.trans_info(requests))

    conn.set_isolation_level(firebirdsql.ISOLATION_LEVEL_SERIALIZABLE)
    cur = conn.cursor()
    cur.execute("select * from foo")
    print(cur.description)
    for c in cur.fetchall():
        print(c)
    conn.close()


