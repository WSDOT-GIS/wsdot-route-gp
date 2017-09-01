Get-ChildItem "**/*.pyc" -Recurse | Remove-Item
Remove-Item build,dist,wsdot.route.egg-info -Recurse -ErrorAction SilentlyContinue