metatypescript
==============

Typescript module - sync. Alternative to CommonJs, AMD and RequireJS


##Setup

```
npm -g install metatypescript
```

You can install terminal-notifier package to have notifications enabled

	brew install terminal-notifier

##Usage
```
metatypescript [--nosound] [--nonotification] [--es5]
```

Metatypescript script will search a **metatypescript.json** file inside the current directory.
If no file is found, the script will create one with default values and will create the lib folder from https://github.com/borisyankov/DefinitelyTyped

**metatypescript.json** config file example:

```
 {
 	//list of module's folders
	"folders":[
		"framework/ghost", 
		"framework/browser",
		"game/battle"
	],
	//if you wanted only one JS file from a module and all its dependencies
	"out":
	{
		"battle/main":"../js/main.js"
	},
	//if true will compile for each module a JS file
	"compile_modules":false
}
```

Inside a submodule's file you can use these keywords to manage dependencies

```
	///<file="File1.ts"/>
	Will write File1 before the current to the compiled JS
	///<module="folder/module/submodule">
	Will add a dependency to folder/module/submodule to this current submodule
	folder/module are not needed if the other submodule is at same level
	If two files into a submodule require same others submodule only one include will be used
	///<lib="jquery">
	will add /lib/jquery/jquery.d.ts file as dependency (theses files can be found at https://github.com/borisyankov/DefinitelyTyped)
```