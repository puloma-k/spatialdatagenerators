#!/bin/bash
for i in 1 2 3 4
do
	curl -o parcel${i}.txt "http://localhost/cgi/generator.py?dist=parcel&card=${i}&geo=box&dim=2&fmt=wkt&dith=0&sran=0.5"
done

