<!-- Example of how the topnav would be stored on the portal then sent to the interventon via AJAX

TODO - need to rewrite from PHP
<?php
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Credentials: true');
header('Access-Control-Allow-Headers: x-requested-with');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
?>

Topnav requires topnav.css as well as Bootstrap. Can rewrite to be indepent of BS.
--->

<!-- Top Nav begins here -->
<div class="container">
    <div class="pull-left nav-logos">
        <!-- Probably need to use absolute links for images -->
        <a href="http://truenth-demo.cirg.washington.edu"><img src="img/logo_truenth.png" /></a>
        <a href="http://us.movember.com"><img src="img/logo_movember.png" /></a>
    </div>
    
    <div class="pull-right nav-links">
        <a href="#" class="btn btn-default">About</a>
        <a href="#" class="btn btn-default">Help</a>
        <a href="#" class="btn btn-default">My Profile</a>
        <a href="index.html" class="btn btn-default">Log Out</a>
        <form class="navbar-form" role="search">
        <div class="form-group">
            <div class="hide-initial" id="search-box">
                <input type="text" class="form-control" placeholder="Search">
            </div>
        </div>
        <button type="submit" class="btn btn-default show-search"><i class="fa fa-search"></i></button>
      </form>
    </div>
</div>
<!-- Top Nav ends here -->