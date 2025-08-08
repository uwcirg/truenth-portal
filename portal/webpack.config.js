const path = require("path");
const webpack = require("webpack");
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");
//const HtmlWebpackPlugin = require("html-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const TerserWebpackPlugin = require("terser-webpack-plugin");
const VueLoaderPlugin = require("vue-loader/lib/plugin");
const crypto = require("crypto");
const JsSrcPath = "./static/js/src";
//const templateDirectory = "/static/templates/";
const crypto_orig_createHash = crypto.createHash;
crypto.createHash = (algorithm) =>
  crypto_orig_createHash(algorithm == "md4" ? "sha256" : algorithm);
const emproResourcesAlias = "eproms_substudy_tailored_content";
module.exports = (env, argv) => {
  console.log(`build mode: ${argv.mode}`); // This will log 'development' or 'production'
  const mode = argv.mode;
  const isDevelopment = mode === "development";
  return {
    mode: mode,
    watch: isDevelopment,
    watchOptions: {
      aggregateTimeout: 300,
      poll: 1000,
      ignored: /node_modules/,
    },
    devtool: isDevelopment ? "eval" : false,
    entry: {
      /* files to be transpiled and optimized */
      account: JsSrcPath + "/accountCreation.js",
      admin: JsSrcPath + "/admin.js",
      assessmentReport: JsSrcPath + "/assessmentReport.js",
      bootstrapTableExtensions: JsSrcPath + "/bootstrapTableExtensions.js",
      CookieMonster: JsSrcPath + "/CookieMonster.js",
      coredata: JsSrcPath + "/coredata.js",
      initialQueries: JsSrcPath + "/initialQueries.js",
      empro: JsSrcPath + "/empro.js",
      gil: JsSrcPath + "/gil.js",
      gilIndex: JsSrcPath + "/gilIndex.js",
      landing: JsSrcPath + "/landing.js",
      main: JsSrcPath + "/main.js",
      longitudinalReport: JsSrcPath + "/longitudinalReport.js",
      orgTreeView: JsSrcPath + "/orgTreeView.js",
      portal: JsSrcPath + "/portal.js",
      profile: JsSrcPath + "/profile.js",
      psaTracker: JsSrcPath + "/psaTracker.js",
      research: JsSrcPath + "/research.js",
      scheduledJobs: JsSrcPath + "/scheduledJobs.js",
      shortcutAlias: JsSrcPath + "/shortcutAlias.js",
      [emproResourcesAlias]: [
        "whatwg-fetch",
        JsSrcPath + `/${emproResourcesAlias}/app.js`,
      ],
      websiteConsentScript: JsSrcPath + "/websiteConsentScript.js",
    },
    output: {
      filename: "[name].bundle.js",
      chunkFilename: "[name].bundle.js",
      path: path.resolve(__dirname, "static/js/dist"),
      publicPath:
        "/static/js/dist/" /* where the bundled files are updated, relative to root - specify this to make sure chunks (including the dynamically generated ones) are being generated in the correct directory */,
      clean: true,
    },
    module: {
      rules: [
        {
          test: /\.js$/,
          exclude: /(node_modules)/,
          use: {
            loader:
              "babel-loader" /*transpile ES2015+ code to browser readable code*/,
          },
        },
        {
          test: /\.vue$/,
          use: "vue-loader",
        },
        {
          test: /\.css$/,
          use: [MiniCssExtractPlugin.loader, "css-loader"],
        },
        {
          test: /\.less$/,
          use: [
            {
              loader: "style-loader", // creates style nodes from JS strings
            },
            {
              loader: "css-loader", // translates CSS into CommonJS
            },
            {
              loader: "less-loader", // compiles Less to CSS
            },
          ],
        },
        {
          test: /\.(png|jpe?g|gif|svg)$/i,
          type: 'asset/inline'
          // type: 'asset/resource', // Handles images as separate files
          // generator: {
          //   filename: '[name].[ext]', // Optional: customize output path
          // },
        },
      ],
    },
    optimization: {
      minimize: true,
      minimizer: [
        new TerserWebpackPlugin({
          terserOptions: {
            compress: {
              comparisons: false,
            },
            mangle: {
              safari10: true,
            },
            output: {
              comments: false,
              ascii_only: true,
            },
            warnings: false,
          },
        }),
        // For webpack v5, you can use the `...` syntax to extend existing minimizers (i.e. `terser-webpack-plugin`), uncomment the next line // `...`,
        new CssMinimizerPlugin(),
      ],
      splitChunks: {
        chunks: (chunk) => chunk.name === emproResourcesAlias,
        cacheGroups: {
          vendors: {
            test: /[\\/]node_modules[\\/]/,
            name: "vendors",
            chunks: "all",
          },
        },
      },
    },
    plugins: [
      // new HtmlWebpackPlugin({
      //   title: "EMPRO Resources",
      //   template: `./static/js/src/${emproResourcesAlias}/app.html`,
      //   //output html file to template directory to be served up, see: https://github.com/uwcirg/truenth-portal/blob/4ffd3a23a1cf69013b818f10f5470ee45c7cc731/portal/views/portal.py#L217
      //   filename: path.join(
      //     __dirname,
      //     `${templateDirectory}/substudy_tailored_content.html`
      //   ),
      //   // favicon: path.join(
      //   //   __dirname,
      //   //   `/static/js/src/${emproResourcesAlias}/assets/favicon.ico`
      //   // ),
      //   chunks: [emproResourcesAlias, "vue"],
      // }),
      new webpack.ProvidePlugin({
        Vue: ["vue/dist/vue.esm.js", "default"],
      }),
      new VueLoaderPlugin(),
      new MiniCssExtractPlugin({
        // Options similar to the same options in webpackOptions.output
        // both options are optional
        filename: "[name].[contenthash].css",
        chunkFilename: "[name].[id].[contenthash].css",
      }),
    ],
  };
};
