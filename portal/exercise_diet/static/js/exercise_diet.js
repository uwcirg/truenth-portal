$(document).ready(function(){
    var fullpath = $(location).attr('pathname').split("/")
    var pathname = "." + fullpath[fullpath.length-1]
    $('#mainNavbar .nav '+pathname).addClass('active');
});

function show_diet(new_item, current_item) {
    $('#'+new_item).on('shown.bs.modal', function(e) {
        $('body').addClass('modal-open');
    });

    $('#'+current_item).modal('hide');
    $('#'+new_item).modal('show');
}

$(function(){

    $('#diet-table tr').on('mouseenter',function(){
        $(this).addClass('row-hover');
        return false;
    });

    $('#diet-table tr').on('mouseleave',function(){
        $(this).removeClass('row-hover');
        return false;
    });

    $('#avoid-foods-table td').on('mouseenter',function(){
        $(this).addClass('cell-hover');
        return false;
    });

    $('#avoid-foods-table td').on('mouseleave',function(){
        $(this).removeClass('cell-hover');
        return false;
    });

});

function show_exercise(new_item, current_item) {
    $('#'+new_item).on('shown.bs.modal', function(e) {
        $('body').addClass('modal-open');
    });

    $('#'+current_item).modal('hide');
    $('#'+new_item).modal('show');
}

$(function(){
    $("input[type='submit']").on("click",function() {
        var zipcode = $("input[name='zipcode']").val();
        var url = "https://www.livestrong.org/ymca-search?distance[postal_code]="+zipcode+"&distance[search_distance]=20&distance[search_units]=mile";
        window.open(url, '_blank');
    });
});

function show_recipe(heading, item, recipe_type) {
    if (recipe_type === 'tip') {
        $('#recipe-modal').addClass('tip');
    }
    else {
        $('#recipe-modal').removeClass('tip');
    }
    $('#recipe-modal').modal('show');
    $( ".modal-body" ).load( "recipe/" + heading + "/" + item );
}

$(function(){

    $('td').on('mouseenter',function(){
        $(this).addClass('cell-hover');
        return false;
    });

    $('td').on('mouseleave',function(){
        $(this).removeClass('cell-hover');
        return false;
    });

});
