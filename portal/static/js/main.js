/*** Portal specific javascript. Topnav.js is separate and will be used across domains. **/

function equalHeightBoxes(passClass) {
    var windowsize = $(window).width();
    // Switch back to auto for small screen or to recalculate on larger
    $('.'+passClass).css("height","auto");
    if (windowsize > 768 && $('.'+passClass).length > 1) {
        var elementHeights = $('.'+passClass).map(function() {
            return $(this).height();
        }).get();
        // Math.max takes a variable number of arguments
        // `apply` is equivalent to passing each height as an argument
        var maxHeight = Math.max.apply(null, elementHeights);
        // Set each height to the max height
        $('.'+passClass).height(maxHeight);
    }
}

// Return an XHR without XHR header so  it doesn't need to be explicitly allowed with CORS
function xhr_function(){
    // Get new xhr object using default factory
    var xhr = jQuery.ajaxSettings.xhr();
    // Copy the browser's native setRequestHeader method
    var setRequestHeader = xhr.setRequestHeader;
    // Replace with a wrapper
    xhr.setRequestHeader = function(name, value) {
        // Ignore the X-Requested-With header
        if (name == 'X-Requested-With') return;
        // Otherwise call the native setRequestHeader method
        // Note: setRequestHeader requires its 'this' to be the xhr object,
        // which is what 'this' is here when executed.
        setRequestHeader.call(this, name, value);
    }
    // pass it on to jQuery
    return xhr;
}
// AJAX callback
function embed_page(data){
    $("#mainNav")
        // Embed data returned by AJAX call into container element
        .html(data)
    // Todo: add "data-*" HTML attribute
}
$(document).ready(function() {
    var initial_xhr = $.ajax({
        url: PORTAL_NAV_PAGE,
        type:'GET',
        contentType:'text/plain',
        //dataFilter:data_filter,
        //xhr: xhr_function,
        crossDomain: true
        //xhrFields: {withCredentials: true},
    }, 'html')
    .done(function(data) {
        embed_page(data);
        //showSearch();
    })
    .fail(function(jqXHR, textStatus, errorThrown) {
        alert("Error loading nav elements from " + PORTAL_HOSTNAME);
    })
    .always(function() {
        // alert( "complete" );
    });

    $("#getStarted").on("click", function(){
        $("#chooseSignIn").fadeOut("fast", function(){
            $("#choosePath").fadeIn();
        });
    });
    $("#btnBrowse").on("click", function(){
        $("#choosePath").fadeOut("fast", function(){
            $("#chooseBrowse").fadeIn();
        });
    });
    $("#btnAnon").on("click", function(){
        $("#choosePath").fadeOut("fast", function(){
            $("#chooseAnon").fadeIn();
        });
    });

    $("[data-ans=no]").on("click", function(){
       $(this).addClass("active");
       $(this).parent().next().fadeIn("slow");
    });

});