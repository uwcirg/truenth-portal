$(document).ready(function(){
	function showSearch() {
		$(".show-search").on("click",function(){
			$("#search-box").fadeIn("slow");
			return false;
		});
	}
	showSearch();
})