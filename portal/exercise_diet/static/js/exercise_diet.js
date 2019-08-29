function show_diet(new_item, current_item) {
    $("#"+new_item).on("shown.bs.modal", function(e) {
        $("body").addClass("modal-open");
    });
    $("#"+new_item).on("hide.bs.modal", function(e) {
        $("body").removeClass("modal-open");
    });
    $("#"+current_item).modal("hide");
    $("#"+new_item).modal("show");
}

function show_exercise(new_item, current_item) {
    $("#"+new_item).on("shown.bs.modal", function(e) {
        $("body").addClass("modal-open");
    });

    $("#"+new_item).on("hide.bs.modal", function(e) {
        $("body").removeClass("modal-open");
    });

    $("#"+current_item).modal("hide");
    $("#"+new_item).modal("show");
}
function show_recipe(heading, item, recipe_type) {
    if (recipe_type === "tip") {
        $("#recipe-modal").addClass("tip");
    }
    else {
        $("#recipe-modal").removeClass("tip");
    }
    $("#recipe-modal").modal("show");
    $(".modal-body").addClass("load");
    $(".modal-body" ).load( "recipe/" + heading + "/" + item, function() {
        setTimeout(function() {
            $(".modal-body").removeClass("load");
            $("#recipe-modal").animate({ scrollTop: 0 }, "slow");
        }, 750);
    });
}
function setActiveMenuLink() {
    var fullpath = $(location).attr("pathname").split("/");
    var pathname = "." + fullpath[fullpath.length-1];
    $("#mainNavbar .nav "+pathname).addClass("active");
}
function setVideoLinkEvent() {
    $(".watch-button-video").on("click", function(e) {
        e.stopPropagation();
        var src = $(".video-module").data("iframe-src");
        if ($("video-module").find("iframe").length === 0) {
            $(".video-module").append("<iframe src='" + src + "' allowfullscreen frameborder='0' />");
        }
        $(this).fadeOut();
    });
}
function setAccordionElementsEvent() {
    $("#Recipe-Accordions [role='tabpanel']").on("shown.bs.collapse", function() {
        $(this).addClass("visited");
    });
    $("#Recipe-Accordions [role='tabpanel']").on("hidden.bs.collapse", function() {
        $(this).removeClass("visited");
    });
}
function setResourcesSubmitEvent() {
    $("#Resources input[type='submit']").on("click",function() {
        var zipcode = $("input[name='zipcode']").val();
        var url = "https://www.livestrong.org/ymca-search?distance[postal_code]="+zipcode+"&distance[search_distance]=20&distance[search_units]=mile";
        window.open(url, "_blank");
    });
}
function setScrollToLinkEvent() {
    $(".js-scroll-to").attr("style", "").on("click", function() {
        $("html, body").animate({
            scrollTop: ($(".anchor").offset().top - 80)
        },1000);
    });
}
function setInitVis() {
    if ($("#Exercise-Diet-Portal").length > 0) {
        $("body").addClass("page-exercise-diet-portal");
    }
    if (!$("#upperBanner").length || !$("#upperBanner").is(":visible")) {
        $("html").addClass("is-upper-banner-closed");
    }
    setTimeout(function() {
        $("main").addClass("active");
    }, 750);
}
function setModalElementsEvent() {
    $("[data-toggle=modal]").on("click touchend", function(e) {
        var target;
        e.preventDefault();
        e.stopPropagation();
        target = $(this).attr("data-target");
        $(target).appendTo("body");
        return setTimeout(function() {
            $(target).modal("show");
        }, 50);
    });
}

$(function(){
    //set active tab
    setActiveMenuLink();
    //bind modal event
    setModalElementsEvent();
    //bind video link event - video link that plays video
    setVideoLinkEvent();
    //bind accordion element event - element as seen in the recipies tab
    setAccordionElementsEvent();
    //Resources 
    setResourcesSubmitEvent();
    //down arrow link event - element seen on top of Hero image
    setScrollToLinkEvent();
    //allow content to load before showing content
    setInitVis();
});
