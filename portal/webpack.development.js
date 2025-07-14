const merge = require("webpack-merge").merge;
const common = require("./webpack.common.js");
/*
 * for DEVELOPMENT
 * run relevant npm script e.g. [npm run develop:js] when developing as any change will trigger a rebuild of the modified(files)
 */
module.exports = merge(common, {
  mode: "development",
  // module: {
  //   rules: [
  //     {
  //       test: /\.less$/,
  //       use: [
  //         {
  //           loader: "style-loader", // creates style nodes from JS strings
  //         },
  //         {
  //           loader: "css-loader", // translates CSS into CommonJS
  //           options: {
  //             sourceMap: true,
  //           },
  //         },
  //         {
  //           loader: "less-loader", // compiles Less to CSS
  //           options: {
  //             sourceMap: true,
  //           },
  //         },
  //       ],
  //     },
  //   ],
  // },
  devtool: "inline-source-map",
});
