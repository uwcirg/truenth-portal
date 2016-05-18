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

// Loading indicator that appears in UI on page loads and when saving
var loader = function(show) {
    if (show) {
        $("#profileForm").addClass("loading");
        $("#loadingIndicator").show();
    } else {
        // Otherwise we'll hide it
        $("#loadingIndicator").fadeOut();
        $("#profileForm").removeClass("loading");
    }
}

var getOrgs = function(userId,onProfile) {

    loader(true);

    $.ajax ({
        type: "GET",
        url: '/api/organization'
    }).done(function(data) {
        $.each(data.entry,function(i,val){
           if (val.partOf) {
               var getParent = val.partOf.reference.split("/").pop();
               var clinic = '<div class="checkbox"><label>' +
                   '<input class="clinic" type="checkbox" name="organization" value="'+
                   val.id +'" data-parent-id="'+getParent+'" />'+
                   val.name +
                   '</label></div>';
               $("#clinics"+getParent).append(clinic);
           }
        });
        getDemo(userId,onProfile);
    }).fail(function() {
        console.log("Problem retrieving data from server.");
        loader();
    });
};

var getDemo = function(userId,onProfile) {
    $.ajax ({
        type: "GET",
        url: '/api/demographics/'+userId
    }).done(function(data) {

        if (onProfile) {
            // Get ethnicity
            $.each(data.extension[0].valueCodeableConcept.coding,function(i,val){
                $("#userEthnicity input:radio[value="+val.code+"]").prop('checked', true);
                // Way to handle non-standard codes - output but hide, for submitting on update
                if ($("#userEthnicity input:radio[value="+val.code+"]").length == 0) {
                    $("#userEthnicity").append("<input class='tnth-hide' type='checkbox' checked name='ethnicity' value='"+val.code+"' data-label='"+val.display+"' />");
                }
            });
            // Get Races
            $.each(data.extension[1].valueCodeableConcept.coding,function(i,val){
                $("#userRace input:checkbox[value="+val.code+"]").prop('checked', true);
                // Way to handle non-standard codes
                if ($("#userRace input:checkbox[value="+val.code+"]").length == 0) {
                    // If there is any non-standard, then check the "other" in the UI
                    $("#userRace input:checkbox[value=2131-1]").prop('checked', true);
                    // Add hidden list of non-standard for form submission
                    $("#userRace").append("<input class='tnth-hide' type='checkbox' checked name='race' value='"+val.code+"' data-label='"+val.display+"' />");
                    //$("#raceOtherVal").fadeToggle();
                }
            });
        } else {
            // For now we assume we're on initial_queries
            $("#terms").fadeIn();
        }

        // Get Orgs
        $.each(data.careProvider,function(i,val){
            var orgID = val.reference.split("/").pop();
            $("body").find("#userOrgs input.clinic:checkbox[value="+orgID+"]").prop('checked', true);
        });
        loader();

    }).fail(function() {
        console.log("Problem retrieving data from server.");
        loader();
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
        $("#saveMsg").hide();
        setTimeout(function(){
            $("#confirmMsg").fadeIn("slow").delay(3000).fadeOut("slow");
            //$("#profileIntro").html("<strong>Your changes have been saved.</strong> Return to the <a href='/'>main portal page</a> {% if current_user.has_roles('admin') %} or <a href='/admin'> user administration</a>{% endif %}.");
            loader();
        }, 400);
    }).fail(function() {
        alert("There was a problem updating your profile. Please try again.");
        loader();
    });
};

var assembleProfile = function(userId) {

    loader(true);

    // Check any parent orgs
    $.each($("#userOrgs input:checkbox:checked"),function(i,v){
        if ($(this).attr("data-parent-id")) {
            $("#userOrgs input:checkbox[value="+$(this).attr("data-parent-id")+"]").prop('checked', true);
        }
    });

    // Grab profile field values - looks for regular and hidden, can be checkbox or radio
    var ethnicityIDs = $("#userEthnicity input:checked").map(function(){
        return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Ethnicity" };
    }).get();
    // Look for race checkboxes, can be hidden
    var raceIDs = $("#userRace input:checkbox:checked").map(function(){
        return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Race" };
    }).get();
    var orgIDs = $("#userOrgs input:checkbox:checked").map(function(){
        return { reference: "api/organization/"+$(this).val() };
    }).get();

    var parentId;
    $.each($("#userOrgs input:checkbox:checked"),function(i,v){
        if ($(this).attr("data-parent-id") && $(this).attr("data-parent-id") != parentId) {
            orgIDs.push({reference: "api/organization/"+$(this).attr("data-parent-id")});
            parentId = $(this).attr("data-parent-id");
        }
    });
    // Testing random codings for race/eth
    //ethnicityIDs.push({code: "2143-6", system: "http://hl7.org/fhir/v3/Ethnicity"});
    //raceIDs.push({code: "1018-1", system: "http://hl7.org/fhir/v3/Race"});
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
    demoArray["careProvider"] = orgIDs;
    //console.log(demoArray);
    /** Send the AJAX **/
    putDemo(userId,demoArray);
}


var assembleOrgs = function(userId) {

    // Check any parent orgs
    $.each($("#userOrgs input:checkbox:checked"),function(i,v){
        if ($(this).attr("data-parent-id")) {
            $("#userOrgs input:checkbox[value="+$(this).attr("data-parent-id")+"]").prop('checked', true);
        }
    });

    var orgIDs = $("#userOrgs input:checkbox:checked").map(function(){
        return { reference: "api/organization/"+$(this).val() };
    }).get();

    var parentId;
    $.each($("#userOrgs input:checkbox:checked"),function(i,v){
        if ($(this).attr("data-parent-id") && $(this).attr("data-parent-id") != parentId) {
            orgIDs.push({reference: "api/organization/"+$(this).attr("data-parent-id")});
            parentId = $(this).attr("data-parent-id");
        }
    });
    var demoArray = {};
    demoArray["resourceType"] = "Patient";
    demoArray["careProvider"] = orgIDs;
    //console.log(demoArray);
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

    // Reveal footer after load to avoid any flashes will above content loads
    $("#homeFooter").show()

});