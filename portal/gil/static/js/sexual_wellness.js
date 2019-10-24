$(function() {
    $(".item__link").on("click", function() {
        $(".item__link").removeClass("active");
        $(this).addClass("active");
        $(".content__item").removeClass("active");
        $(".content__item[data-group="+ $(this).attr("data-group") + "]").addClass("active");
    });
    var activeItemLinkGroup = $(".item__link.active").attr("data-group");
    if (activeItemLinkGroup) {
        $(".content__item[data-group="+activeItemLinkGroup+"]").addClass("active");
    }
    $(".content__item .title").on("click", function() {
        $(".content__item").removeClass("active");
        $(this).closest(".content__item").toggleClass("active");
    });
});
