const path = require("path");
const webpack = require("webpack");
const JsSrcPath = "./static/js/src";
const VueLoaderPlugin = require("vue-loader/lib/plugin");
const crypto = require("crypto");
const crypto_orig_createHash = crypto.createHash;
crypto.createHash = algorithm => crypto_orig_createHash(algorithm == "md4" ? "sha256" : algorithm);
module.exports = {
    entry: { /* files to be transpiled and optimized */
        "account": JsSrcPath+"/accountCreation.js",
        "admin": JsSrcPath+"/admin.js",
        "assessmentReport": JsSrcPath+"/assessmentReport.js",
        "bootstrapTableExtensions": JsSrcPath+"/bootstrapTableExtensions.js",
        "CookieMonster": JsSrcPath+"/CookieMonster.js",
        "coredata": JsSrcPath+"/coredata.js",
        "initialQueries": JsSrcPath+"/initialQueries.js",
        "empro": JsSrcPath+"/empro.js",
        "gil": JsSrcPath+"/gil.js",
        "gilIndex": JsSrcPath+"/gilIndex.js",
        "landing": JsSrcPath+"/landing.js",
        "main": JsSrcPath+"/main.js",
        "longitudinalReport": JsSrcPath+"/longitudinalReport.js",
        "orgTreeView": JsSrcPath+"/orgTreeView.js",
        "portal": JsSrcPath+"/portal.js",
        "profile": JsSrcPath+"/profile.js",
        "psaTracker": JsSrcPath+"/psaTracker.js",
        "research": JsSrcPath+"/research.js",
        "scheduledJobs": JsSrcPath+"/scheduledJobs.js",
        "shortcutAlias": JsSrcPath+"/shortcutAlias.js",
        "websiteConsentScript": JsSrcPath+"/websiteConsentScript.js"
    },
    output: {
        filename: "[name].bundle.js",
        chunkFilename: "[name].bundle.js",
        path: path.resolve(__dirname, 'static/js/dist'),
        publicPath: "/static/js/dist/"  /* where the bundled files are updated, relative to root - specify this to make sure chunks (including the dynamically generated ones) are being generated in the correct directory */
    },
    module: {
        rules: [
            {
                test: /\.js$/,
                exclude:/(node_modules)/,
                use: {
                    loader: "babel-loader" /*transpile ES2015+ code to browser readable code*/
                }
            },
            {
                test: /\.vue$/,
                use: 'vue-loader'
            }
        ]
    },
    plugins: [
        new webpack.SourceMapDevToolPlugin({ /*create sourcemap for bundled file - for ease of debugging in case of error */
            filename: '../../maps/[file].map',
        }),
        new VueLoaderPlugin()
    ]
};
