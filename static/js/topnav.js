function showSearch() {
	$("body").on("click",".show-search",function(){
		$("#search-box").fadeIn("slow");
		return false;
	});
}
$(document).ready(function(){
	showSearch();
});