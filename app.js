const Koa = require('koa')
const Router = require('koa-router')
const app = new Koa()
const router = new Router()

const views = require('koa-views')
const co = require('co')
const convert = require('koa-convert')
const json = require('koa-json')
const onerror = require('koa-onerror')
const bodyparser = require('koa-bodyparser')
const logger = require('koa-logger')
const debug = require('debug')('koa2:server')
const path = require('path')

// dependencies for uploads
const fs = require('fs');
const os = require('os');
const koaBody = require('koa-body');

// dependencies for postgres
const { Client } = require('pg')

// dependencies for api
const send = require('koa-send');

const config = require('./config')
const routes = require('./routes')

const packageUploadDir = config.packageUploadDir || os.tmpdir()

// allow multipart
app.use(koaBody({ multipart: true }));

// error handler
onerror(app)

// middleware
app.use(bodyparser())
  .use(json())
  .use(logger())
  .use(require('koa-static')(__dirname + '/public'))
  .use(views(path.join(__dirname, '/views'), {
    options: {settings: {views: path.join(__dirname, 'views')}},
    map: {'pug': 'pug'},
    extension: 'pug'
  }))
  .use(router.routes())
  .use(router.allowedMethods())

// db connection
const client = new Client({
  host: config.db.host,
  port: config.db.port,
  user: config.db.user,
  password: config.db.pass,
  database: config.db.db,
  ssl: {
    rejectUnauthorized: false
  }
})

client.connect(err => {
  if (err) {
    console.error('Database connection error', err.stack)
  } else {
    console.log('Database connected at %s:%d', config.db.host, config.db.port)
  }
})

// logger
app.use(async (ctx, next) => {
  const start = new Date()
  await next()
  const ms = new Date() - start
  console.log(`${ctx.method} ${ctx.url} - $ms`)
})

// routes
router.get('/', async (ctx, next) => {
  // ctx.body = 'Hello World'
  ctx.state = {
    title: 'WACCANDA'
  }
  await ctx.render('index', ctx.state)
})

router.get('/upload', async (ctx, next) => {
  ctx.state = {
    title: 'WACCANDA Upload'
  }
  await ctx.render('upload', ctx.state)
})

router.get('/error', async (ctx, next) => {
  ctx.state = {
    title: 'Error 415: Unacceptable content type',
    error: new Error(415, 'UPLOAD ERROR'),
    message: 'ERROR 415: Please upload a .wacc file!'
  }
  await ctx.render('error', ctx.state)
})

router.get('/download', async (ctx, next) => {
  await ctx.render('download')
})

router.post('/upload', async ctx => {
  // TODO: CHECK UPLOAD IS SAFE!!!!!!
  const file = ctx.request.files.file;
  var name = file.name;
  if (name.substring(name.length - 5, name.length) != '.wacc') {
    // Invalid file type!!
    console.log("attempted upload of invalid file type '%s'!", name);
    ctx.redirect('/error');
    return;
  }
  name = name.substring(0, name.length - 5) + '_' + new Date().getTime();
  const reader = fs.createReadStream(file.path);
  const stream = fs.createWriteStream(path.join(packageUploadDir, name));
  reader.pipe(stream);
  console.log('uploading %s -> %s', file.name, stream.path);
  ctx.redirect('/');
});

router.post('/api/install/:package/:version', async (ctx, next) => {
  const package = ctx.params.package;
  const version = ctx.params.version;

  let path = '';
  const latestQuery = 'SELECT file_location FROM packages LEFT JOIN package_versions \
                        ON package_versions.package_id=packages.id WHERE UPPER(package_name)=UPPER($1) \
                        ORDER BY upload_ts DESC LIMIT 1'
  const versionQuery = 'SELECT file_location FROM packages LEFT JOIN package_versions \
                        ON package_versions.package_id=packages.id WHERE UPPER(package_name)=UPPER($1) \
                        AND UPPER(version_number)=UPPER($2)'
  try {
    const res = await client.query(version == 'latest' ? latestQuery : versionQuery, version == 'latest' ? [package] : [package, version]);
    if (res.rows.length == 0) {
      ctx.body = 'not found';
    }
    path = res.rows[0]['file_location'];
  
    try {
      ctx.attachment(path); 
      console.log('downloading %s', package);
      await send(ctx, path);
    } catch(e) {
      ctx.body = 'missing';
      console.log(e.message);
      console.log("MISSING PACKAGE!")
    }
  } catch (e) {
    console.log(e.stack);
  }
});


routes(router)
app.on('error', function(err, ctx) {
  console.log(err)
  logger.error('server error', err, ctx)
})

module.exports = app.listen(config.port, () => {
  console.log(`Listening on http://localhost:${config.port}`)
})
