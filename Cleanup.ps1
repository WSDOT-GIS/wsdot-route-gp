Get-ChildItem "**/*.pyc" -Recurse | Remove-Item
Remove-Item build,dist,wsdotroute.egg-info -Recurse -ErrorAction SilentlyContinue
Remove-Item .\src\wsdotroute\esri\help -Recurse -ErrorAction SilentlyContinue
Get-ChildItem "**\help\gp\toolboxes\*" -Recurse | Remove-Item