-- Ayudante: recibe concursos://descargar/<num> desde el buscador y ejecuta descargar.py
on open location theURL
	set marca to "descargar/"
	set p to offset of marca in theURL
	if p is 0 then return
	set theID to text (p + (length of marca)) thru -1 of theURL
	set theID to do shell script "python3 -c \"import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1]))\" " & quoted form of theID
	set cmd to "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH; cd ~/Downloads/concursos && python3 descargar.py " & quoted form of theID & " >> /tmp/concursos-descarga.log 2>&1"
	try
		do shell script cmd
	on error e
		display notification e with title "Concursos"
	end try
end open location

on run
	display dialog "Este ayudante se abre solo desde el buscador de concursos." buttons {"OK"} default button 1
end run
