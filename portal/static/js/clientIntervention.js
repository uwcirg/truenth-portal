$(document).ready(function(){ /*global $ */
    $("#confirmDel").popover({
        html : true, //internal use, so no need to translate here?
        content: "Are you sure you want to delete this app?<br /><br /><button type='submit' name='delete' value='delete' class='btn-tnth-primary btn'>Delete Now</button> &nbsp; <div class='btn btn-default' id='cancelDel'>Cancel</div>"
    });
    $("body").on("click","#cancelDel",function(){
        $("#confirmDel").popover("hide");
    });

});
