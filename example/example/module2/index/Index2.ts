//include submodule submodulemain from other module

///<module="module1/submodulemain"/>
module module2.index
{
	export class Index2 extends module1.submodulemain.Index
	{
		public name():string
		{
			return super.name()+"/index2";
		}
	}
}