const webpack = require("webpack");
const path = require("path");
const TerserWebpackPlugin = require("terser-webpack-plugin");
const OptimizeCssAssetsPlugin = require("optimize-css-assets-webpack-plugin");
const FileManagerPlugin = require('filemanager-webpack-plugin');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const vendorPath = './src/vendors';
const VueLoaderPlugin = require("vue-loader/lib/plugin");

module.exports = function(_env, argv) {
  const isProduction = argv && argv.mode === "production";
  const isDevelopment = !isProduction;
  /*
   * output to static file for ease of development
   */
  const rootDirectory = isDevelopment?"../static":"/dist";
  const outputDirectory = rootDirectory+"/bundle";
  const templateDirectory = `${rootDirectory}/templates`;
  return {
    entry:  ['whatwg-fetch', path.join(__dirname, './src/app.js')],
    watchOptions: {
      aggregateTimeout: 300,
      poll: 1000
    },
    output: {
      path: path.join(__dirname, outputDirectory),
      /*
       * create a new hash for each new build
       */
      filename: `app.bundle.[name]${isProduction?'-[hash:6]':''}.js`,
      publicPath: "/static/bundle/",
      devtoolModuleFilenameTemplate: '[absolute-resource-path]',
      devtoolFallbackModuleFilenameTemplate: '[absolute-resource-path]?[hash]'
    },
    resolve: {
        extensions: ['.js', '.vue'],
        alias: {
          'jquery': path.join(__dirname, '/node_modules/jquery/dist/jquery.min.js')
        }
    },
    devtool: 'inline-cheap-module-source-map',
    module: {
      rules: [
        {
          test: require.resolve('jquery'),
          loader: 'expose-loader',
          options: {
            exposes: ['$', 'jQuery!jquery']
          },
        },
        {
          test: /\.(woff2|eot|ttf|woff|otf)?(\?v=[0-9]\.[0-9]\.[0-9])?$/,
          //use: 'url-loader?limit=10000',
          loader: "file-loader",
          options: {
            name: "[name].[ext]"
          }
        },
        {
          test: /\.(ttf|svg|png|jpe?g|gif)(\?[\s\S]+)?$/,
          loader: 'file-loader',
          options: {
            name: "[name].[ext]"
          }
        },
        {
          test: /\.(js)$/,
          exclude: [/node_modules/, path.resolve(__dirname, vendorPath)],
          loader: 'babel-loader',
          query: {
            presets: [
              ['@babel/preset-env'],
            ],
          },
        },
        {
          test: /\.css$/,
          use: ['style-loader', 'css-loader']
        },
        {
          test: /\.less$/,
          use: [
            {
              loader: 'style-loader', // creates style nodes from JS strings
            },
            {
              loader: 'css-loader', // translates CSS into CommonJS
              options: {
                sourceMap: isDevelopment ? true: false
              }
            },
            {
              loader: 'less-loader', // compiles Less to CSS
              options: {
                sourceMap: isDevelopment ? true: false
              },
            },
          ],
        },
        {
          test: /\.vue$/,
          use: 'vue-loader'
        }
      ],
    },
    plugins: [
      new VueLoaderPlugin(),
      //new CleanWebpackPlugin(),
      new HtmlWebpackPlugin({
        title: "Substudy Tailored Content",
        template: path.join(__dirname, '/src/app.html'),
        filename: path.join(__dirname, `${templateDirectory}/substudy_tailored_content.html`),
        favicon: path.join(__dirname, '/src/assets/favicon.ico'),
      }),
      new webpack.ProvidePlugin(
        { 
          Promise: 'es6-promise',
          $: 'jquery',
          jquery: 'jquery',
          jQuery: 'jquery',
          'window.jQuery': 'jquery',
          Vue: ['vue/dist/vue.esm.js', 'default'],
        }
      ),
      new webpack.DefinePlugin({
        "process.env.NODE_ENV": JSON.stringify(
          isProduction ? "production" : "development"
        )
      }),
      new FileManagerPlugin({
        onStart: {
          delete: [
            path.join(__dirname, '/dist')
          ]
        }
      })
    ],
    optimization: {
      minimize: isProduction,
      minimizer: [
        new TerserWebpackPlugin({
          terserOptions: {
            compress: {
              comparisons: false
            },
            mangle: {
              safari10: true
            },
            output: {
              comments: false,
              ascii_only: true
            },
            sourceMap: !isProduction,
            warnings: false
          }
        }),
        new OptimizeCssAssetsPlugin({
          verbose: true
        }),
      ],
      splitChunks: {
        chunks: "all",
        minSize: 0,
        maxInitialRequests: Infinity,
        cacheGroups: {
          vendors: {
            test: /[\\/]node_modules[\\/]/,
            name(module, chunks, cacheGroupKey) {
              const packageName = module.context.match(
                /[\\/]node_modules[\\/](.*?)([\\/]|$)/
              )[1];
              return `${cacheGroupKey}.${packageName.replace("@", "")}`;
            }
          },
          common: {
            minChunks: 2,
            priority: -10
          }
        }
      }
    }
  };
};
