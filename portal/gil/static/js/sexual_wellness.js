$(function() {
    $(".item__link").on("click", function() {
        $(".item__link").removeClass("active");
        $(this).addClass("active");
        $(".content__item").hide().removeClass("active");
        $(".content__item[data-group="+ $(this).attr("data-group") + "]").fadeIn().addClass("active");
    });
    var activeItemLinkGroup = $(".item__link.active").attr("data-group");
    if (activeItemLinkGroup) {
        $(".content__item[data-group="+activeItemLinkGroup+"]").fadeIn().addClass("active");
    }
});
