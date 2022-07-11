var requestAttempts = 0;
var WORKER_REQUEST_TIMEOUT_INTERVAL = 5000;
function sendRequest(url, params, callback) { //XHR request in pure JavaScript
    requestAttempts++;
    var xhr;
    var ensureReadiness = function() {
        if (xhr.readyState < 4) {
            return;
        }
        // all is well
        if (xhr.status === 200) {
            callback(xhr);
            requestAttempts = 0;
            return;
        }
        if (requestAttempts < 3) {
            setTimeout(function() {
                sendRequest(url, params, callback);
            }, WORKER_REQUEST_TIMEOUT_INTERVAL);
            return;
        }
        requestAttempts = 0;
        callback(xhr);
        return;
    };
    if (typeof XMLHttpRequest !== "undefined") {
        xhr = new XMLHttpRequest();
    } else {
        var versions = ["MSXML2.XmlHttp.5.0",
            "MSXML2.XmlHttp.4.0",
            "MSXML2.XmlHttp.3.0",
            "MSXML2.XmlHttp.2.0",
            "Microsoft.XmlHttp"
        ];
        for (var i = 0; !xhr && i < versions.length; i++) {
            try {
                xhr = new ActiveXObject(versions[i]); /*global ActiveXObject */
                break;
            } catch (e) {
                xhr = null;
            }
        } // end for
    }
    params = params || {};
    if (params.data && params.type === "GET") { //for request with method of 'GET' data need to be serialized format otherwise it is not sent with the request, more info: https://plainjs.com/javascript/ajax/send-ajax-get-and-post-requests-47/
        url += "?" + (typeof params.data === "string" ? data : Object.keys(params.data).map( //no access to JQuery so do this in pure JS
            function(dataItem){ return encodeURIComponent(dataItem) + '=' + encodeURIComponent(params.data[dataItem]) }
        ).join('&'));
    }
    xhr.timeout = params.timeout || WORKER_REQUEST_TIMEOUT_INTERVAL;
    xhr.open("GET", url, true);
    if (!params.cache) {
        xhr.setRequestHeader("cache-control", "no-cache");
        xhr.setRequestHeader("expires", "-1");
        xhr.setRequestHeader("pragma", "no-cache"); //legacy HTTP 1.0 servers and IE support
    }
    for (var param in params) {
        if (params.hasOwnProperty(param)) {
            xhr.setRequestHeader(param, params[param]);
        }
    }
    xhr.onreadystatechange = ensureReadiness;
    xhr.send("");
}
addEventListener("message", function(e) {
    if (!e.data.url) {
        postMessage({error: "Url is required"});
    } else {
        sendRequest(e.data.url, e.data.params, function(xhr) {
            if (xhr.status === 200) {
                postMessage(xhr.responseText);
            } else {
                postMessage(JSON.stringify({
                    "error": "Error ocurred process request, url " + e.data.url,
                    "status": xhr.status,
                    "responseText": (xhr.responseText).replace(/\'\"/g, "")
                }));
            }
        });
    }
}, false);
