function showSearch() {
	$("body").on("click",".container",function(){
		$("#search-box").fadeIn("slow");
		return false;
	});
}
$(document).ready(function(){
	showSearch();
});