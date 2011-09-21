rem #{'encoding': 'utf-8',
rem # 'listen_interface': 'eth0',
rem # 'logging': 'DEBUG',
rem # 'logging_output': 'stdout',
rem # 'owner': 'brisa',
rem # 'version': '0.10.0',
rem # 'webserver_adapter': 'circuits.web'}

python \Python26\Scripts\brisa-conf -i brisa
python \Python26\Scripts\brisa-conf -d -s brisa
python \Python26\Scripts\brisa-conf -s brisa -p encoding utf-8
python \Python26\Scripts\brisa-conf -s brisa -p listen_interface eth0
python \Python26\Scripts\brisa-conf -s brisa -p logging DEBUG
python \Python26\Scripts\brisa-conf -s brisa -p logging_output stdout
python \Python26\Scripts\brisa-conf -s brisa -p owner brisa
python \Python26\Scripts\brisa-conf -s brisa -p version 0.10.0
python \Python26\Scripts\brisa-conf -s brisa -p webserver_adapter cherrypy
rem python \Python26\Scripts\brisa-conf -s brisa -p webserver_adapter circuits.web
python \Python26\Scripts\brisa-conf -i brisa
