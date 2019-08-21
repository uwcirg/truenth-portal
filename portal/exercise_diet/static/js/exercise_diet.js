$(document).ready(function(){
    var fullpath = $(location).attr('pathname').split("/");
    var pathname = "." + fullpath[fullpath.length-1];
    $('#mainNavbar .nav '+pathname).addClass('active');
});

function show_diet(new_item, current_item) {
    $('#'+new_item).on('shown.bs.modal', function(e) {
        $('body').addClass('modal-open');
    });
    $('#'+new_item).on('hide.bs.modal', function(e) {
        $('body').removeClass('modal-open');
    });
    $('#'+current_item).modal('hide');
    $('#'+new_item).modal('show');
}

$(function(){

    setTimeout(function() {
        $("main").addClass("active");
    }, 500);

    // $('#diet-table tr').on('mouseenter',function(){
    //     $(this).addClass('row-hover');
    //     return false;
    // });

    // $('#diet-table tr').on('mouseleave',function(){
    //     $(this).removeClass('row-hover');
    //     return false;
    // });

    // $('#avoid-foods-table td').on('mouseenter',function(){
    //     $(this).addClass('cell-hover');
    //     return false;
    // });

    // $('#avoid-foods-table td').on('mouseleave',function(){
    //     $(this).removeClass('cell-hover');
    //     return false;
    // });

    $('[data-toggle=modal]').on('click touchend', function(e) {
        var target;
        e.preventDefault();
        e.stopPropagation();
        target = $(this).attr('data-target');
        $(target).appendTo('body');
        return setTimeout(function() {
            $(target).modal('show');
        }, 50);
    });
    $(".watch-button-video").on("click", function(e) {
        e.stopPropagation();
        var src = $(".video-module").data("iframe-src");
        if ($("video-module").find("iframe").length === 0) {
            $(".video-module").append("<iframe src='" + src + "' allowfullscreen frameborder='0' />");
        }
        $(this).fadeOut();
    });
    $("#Recipe-Accordions [role='tabpanel']").on("shown.bs.collapse", function() {
        $(this).addClass("visited");
    });
    $("#Recipe-Accordions [role='tabpanel']").on("hidden.bs.collapse", function() {
        $(this).removeClass("visited");
    });
});

function show_exercise(new_item, current_item) {
    $('#'+new_item).on('shown.bs.modal', function(e) {
        $('body').addClass('modal-open');
    });

    $('#'+new_item).on('hide.bs.modal', function(e) {
        $('body').removeClass('modal-open');
    });

    $('#'+current_item).modal('hide');
    $('#'+new_item).modal('show');
}

$(function(){
    $("#Resources input[type='submit']").on("click",function() {
        var zipcode = $("input[name='zipcode']").val();
        var url = "https://www.livestrong.org/ymca-search?distance[postal_code]="+zipcode+"&distance[search_distance]=20&distance[search_units]=mile";
        window.open(url, '_blank');
    });
});

function show_recipe(heading, item, recipe_type) {
    if (recipe_type === "tip") {
        $("#recipe-modal").addClass("tip");
    }
    else {
        $("#recipe-modal").removeClass("tip");
    }
    $('#recipe-modal').modal('show');
    $(".modal-body").addClass("load");
    $(".modal-body" ).load( "recipe/" + heading + "/" + item, function() {
        setTimeout(function() {
            $(".modal-body").removeClass("load");
        }, 500);
    });
    // $("#recipe-modal").on("show.bs.modal", function() {
    //     $( ".modal-body" ).load( "recipe/" + heading + "/" + item, function() {
    //         setTimeout(function() {
    //             $(".modal-body").removeClass("load");
    //         }, 500);
    //     });
    // });
    // $(this).removeClass("load");
    // $("#recipe-modal").on("shown.bs.modal", function() {
    //     setTimeout(function() {
    //         $(".modal-body").removeClass("load");
    //     }, 150);
    // });
   
    
}

// $(function(){

//     $("td').on('mouseenter',function(){
//         $(this).addClass('cell-hover');
//         return false;
//     });

//     $('td').on('mouseleave',function(){
//         $(this).removeClass('cell-hover');
//         return false;
//     });

// });

$(document).ready(function() {
    if ($("#Exercise-Diet-Portal").length > 0) {
        //setTimeout(function() {
        $("body").addClass("page-exercise-diet-portal");
        //}, 100);
    }
    $(".js-scroll-to").attr("style", "").on("click", function() {
        $("html, body").animate({
            scrollTop: ($(".anchor").offset().top - 80)
        },1000);
    });
});
