#!/usr/local/bin/python3
import os
import csv
from urllib import parse
import subprocess

url = os.environ["REQUEST_URI"]

pDict = dict(parse.parse_qsl(parse.urlparse(url).query))
oFilePath = "test"
curwd = "/Users/puloma/Code/generator/html/cgi"
cmd = [curwd + "/generator.py"]

cmd.append("-t")
cmd.append(pDict["dist"])
cmd.append("-c")
cmd.append(pDict["card"])
cmd.append("-g")
cmd.append(pDict["geo"])
cmd.append("-d")
cmd.append(pDict["dim"])
cmd.append("-f")
cmd.append(pDict["fmt"])
cmd.append("-o")
cmd.append(oFilePath)


if(pDict["dist"] == "diagonal"):
	cmd.append("-p")
	cmd.append(pDict["per"])
	cmd.append("-b")
	cmd.append(pDict["buf"])
elif(pDict["dist"] == "bit"):
	cmd.append("-q")
	cmd.append(pDict["prob"])
	cmd.append("-n")
	cmd.append(pDict["dig"])
elif(pDict["dist"] == "parcel"):
	cmd.append("-r")
	cmd.append(pDict["sran"])
	cmd.append("-e")
	cmd.append(pDict["dith"])


compProc = subprocess.run(cmd, cwd=curwd)
# , text=True, stdout=subprocess.PIPE

print ("Content-type:text/html;charset=utf-8\r\n\r\n")
print ('<html>')
print ('<head>')
print ('<title>Generator Data</title>')
print ('</head>')
print ('<body>')
print ('<h2>Generator Data</h2>')
# print (" ".join(cmd) +  " " + '<br/><p/>')
print ('<table border="1">')

with open(curwd + "/output/" + oFilePath + ".csv") as csvFile :
	dataReader = csv.reader(csvFile)
	for row in dataReader:
		print('<tr>')
		for col in row:
			print('<td>')
			print(col)
			print('</td>')
		print('</tr>')
		
print ('</table>')		
print ('</body>')
print ('</html>')


