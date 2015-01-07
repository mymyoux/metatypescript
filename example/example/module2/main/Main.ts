//include module index
///<module="index"/>
module module2.main
{
	export class Main
	{
		constructor()
		{

		}
		public getIndexName():string
		{
			var index:module2.index.Index2 = new module2.index.Index2();
			return index.name();
		}

	}
}