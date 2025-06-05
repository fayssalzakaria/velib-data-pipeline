#!/bin/bash
airflow db init
exec airflow webserver
