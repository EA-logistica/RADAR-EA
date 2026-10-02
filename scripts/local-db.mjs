import EmbeddedPostgres from 'embedded-postgres';
const pg = new EmbeddedPostgres({databaseDir:'.runtime/postgres',user:'radar',password:'radar_local',port:54329,persistent:true,initdbFlags:['--encoding=UTF8','--locale=C'],postgresFlags:['-h','127.0.0.1']});
await pg.initialise();
await pg.start();
try { await pg.createDatabase('radar'); } catch(e) { if (!String(e).includes('already exists')) throw e; }
console.log('PostgreSQL ready at localhost:54329/radar');
for (const signal of ['SIGINT','SIGTERM']) process.on(signal,async()=>{await pg.stop();process.exit(0)});
setInterval(()=>{},60000);
