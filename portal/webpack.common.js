const path = require("path");
const webpack = require("webpack");
const JsSrcPath = "./static/js/src";
module.exports = {
    entry: {
        "main": JsSrcPath+"/main.js",
        "gil": JsSrcPath+"/gil.js",
        "account": JsSrcPath+"/accountCreation.js",
        "admin": JsSrcPath+"/admin.js",
        "CookieMonster": JsSrcPath+"/CookieMonster.js",
        "profile": JsSrcPath+"/profile.js",
        "initialQueries": JsSrcPath+"/initialQueries.js",
        "coredata": JsSrcPath+"/coredata.js",
        "psaTracker": JsSrcPath+"/psaTracker.js",
        "orgTreeView": JsSrcPath+"/orgTreeView.js",
        "assessmentReport": JsSrcPath+"/assessmentReport.js",
        "websiteConsentScript": JsSrcPath+"/websiteConsentScript.js",
        "reportingDashboard": JsSrcPath+"/reportingDashboard.js",
        "scheduledJobs": JsSrcPath+"/scheduledJobs.js"
    },
    output: {
        filename: "[name].bundle.js",
        path: path.resolve(__dirname, 'static/js/dist')
    },
    module: {
        rules: [
            {
                test: /\.js$/,
                exclude:/(node_modules)/,
                use: {
                    loader: "babel-loader" /*transpire ES2015+ code to browser readable code*/
                }
            }
        ]
    },
    plugins: [
        new webpack.SourceMapDevToolPlugin({ /*create sourcemap for bundled file - for ease of debugging in case of error */
            filename: '../../maps/[file].map',
        })
    ]
};

