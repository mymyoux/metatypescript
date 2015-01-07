//force Main.ts to be included before this current file
///<file="Main"/>
//will include jquery.d.ts from /lib folder
///<lib="jquery"/>
var main:module2.main.Main = new module2.main.Main();
$(function()
{

	$(".name").text(main.getIndexName());

});