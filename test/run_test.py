#!/bin/sh

cd unit
./gocad_importer_test.py
[ $? -ne 0 ] && exit 1
cd ../regression
./reg_run.sh
[ $? -ne 0 ] && exit 1
cd ../../scripts/lib/db
./db_tables.py

