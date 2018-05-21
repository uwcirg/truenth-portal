var requestAttempts = 0;
function sendRequest(url, params, callback) { //XHR request in pure JavaScript
    requestAttempts++;
    var xhr;
    var ensureReadiness = function() {
        if (xhr.readyState < 4) {
            return;
        }
        // all is well
        if (xhr.readyState === 4) {
            if (xhr.status !== 200) {
                if (requestAttempts < 3) {
                    setTimeout(function() {
                        sendRequest(url, params, callback);
                    }, 2000);
                } else {
                    requestAttempts = 0;
                    callback(xhr);
                    return;
                }
            } else {
                callback(xhr);
                requestAttempts = 0;
            }
        }
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
        for (var i = 0, len = versions.length; i < len; i++) {
            try {
                xhr = new ActiveXObject(versions[i]); /*global ActiveXObject */
                break;
            } catch (e) {}
        } // end for
    }
    xhr.onreadystatechange = ensureReadiness;
    xhr.open("GET", url, true);
    if (params) {
        for (var param in params) {
            if (params.hasOwnProperty(param)) {
                xhr.setRequestHeader(param, params[param]);
            }
        }
    }
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
