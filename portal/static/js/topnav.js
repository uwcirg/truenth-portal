function showSearch() {
	$("body").on("click",".show-search",function(){
        if ($(this).hasClass("now-open")) {
            $("#search-box").hide();
        } else {
            $(this).addClass("now-open");
            $("#search-box").fadeIn("slow")
        }
		return false;
	});
}
$(document).ready(function(){
	showSearch();
});