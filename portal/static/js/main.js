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

var getDemo = function(userId) {
    $.ajax ({
        type: "GET",
        url: '/api/demographics/'+userId
    }).done(function(data) {
        console.log(data);
        // Get ethnicity
        $.each(data.extension[0].valueCodeableConcept.coding,function(i,val){
            $("#userEthnicity input:radio[value="+val.code+"]").prop('checked', true);
            // Way to handle non-standard codes
            if ($("#userEthnicity input:radio[value="+val.code+"]").length == 0) {
                console.log('other one');
            }
        });
        // Get Races
        $.each(data.extension[1].valueCodeableConcept.coding,function(i,val){
            $("#userRace input:checkbox[value="+val.code+"]").prop('checked', true);
            // Way to handle non-standard codes
            if ($("#userRace input:checkbox[value="+val.code+"]").length == 0) {
                console.log('other one');
            }
        });
    }).fail(function() {
        console.log("Problem retrieving data from server.")
    });
};

// Used on profile page to submit user demo data
var putDemo = function(userId,demoArray,isAdmin) {
    $.ajax ({
        type: "PUT",
        url: '/api/demographics/'+userId,
        contentType: "application/json; charset=utf-8",
        dataType: 'json',
        data: JSON.stringify(demoArray)
    }).done(function() {
        $("#saveMsg").hide()
        setTimeout(function(){
            $("#confirmMsg").fadeIn("slow").delay(3000).fadeOut("slow");
            //$("#profileIntro").html("<strong>Your changes have been saved.</strong> Return to the <a href='/'>main portal page</a> {% if current_user.has_roles('admin') %} or <a href='/admin'> user administration</a>{% endif %}.");
            $("#profileForm").removeClass("loading");
            $("#loadingIndicator").fadeOut();
        }, 1200);
    }).fail(function() {
        alert("There was a problem updating your profile. Please try again.");
        $("#loadingIndicator").fadeOut();
        $("#profileForm").removeClass("loading");
    });
};

var assembleProfile = function(userId) {

    $("#profileForm").addClass("loading");
    $("#loadingIndicator").show();

    // Grab profile field values
    var ethnicityIDs = $("#userEthnicity input:radio:checked").map(function(){
        return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Ethnicity" };
    }).get();
    var raceIDs = $("#userRace input:checkbox:checked").map(function(){
        return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Race" };
    }).get();
    // Testing random code
    //ethnicityIDs.push({code: "2143-6", system: "http://hl7.org/fhir/v3/Ethnicity"});

    // Put form data into FHIR array
    var demoArray = {};
    demoArray["resourceType"] = "Patient";
    demoArray["birthDate"] = $("input[name=birthDate]").val();
    demoArray["gender"] = $("input[name=sex]:checked").val();
    demoArray["name"] = {
        "given": $("input[name=firstname]").val(),
        "family": $("input[name=lastname]").val()
    };
    demoArray["telecom"] = [
        { "system": "email", "value": $("input[name=email]").val() },
        { "system": "phone", "value": $("input[name=phone]").val() }
    ];
    demoArray["extension"] = [
        { "url": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
            "valueCodeableConcept": {
                "coding": ethnicityIDs
            }
        },
        { "url": "http://hl7.org/fhir/StructureDefinition/us-core-race",
            "valueCodeableConcept": {
                "coding": raceIDs
            }
        }
    ];
    /** Send the AJAX **/
    putDemo(userId,demoArray);
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

    //$("#btnBrowse").on("click", function(){
    //    $("#choosePath").fadeOut("fast", function(){
    //        $("#chooseBrowse").fadeIn();
    //    });
    //});
    $("#btnAnon").on("click", function(){
        $("#choosePath").fadeOut("fast", function(){
            $("#chooseAnon").fadeIn();
        });
    });

    $("[data-ans=no]").on("click", function(){
       $(this).addClass("active");
       $(this).parent().next().fadeIn("slow");
    });

    // Reveal footer after load to avoid any flashes will above content loads
    $("#homeFooter").show()

});