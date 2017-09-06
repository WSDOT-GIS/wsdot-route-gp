Get-ChildItem "**/*.pyc" -Recurse | Remove-Item
Remove-Item build,dist,wsdot.route.egg-info -Recurse -ErrorAction SilentlyContinue
Remove-Item .\src\wsdot\route\esri\help -Recurse -ErrorAction SilentlyContinue
Get-ChildItem "**\help\gp\toolboxes\*" -Recurse | Remove-Item