import { writeFileSync } from 'node:fs';

function serviceOrigin(name) {
    let url;
    try {
        url = new URL(process.env[name]);
    } catch {
        throw new Error(`Set ${name} to the deployed service HTTPS origin.`);
    }
    if (url.protocol !== 'https:' || url.username || url.password ||
        url.pathname !== '/' || url.search || url.hash) {
        throw new Error(`${name} must be an HTTPS origin without credentials or a path.`);
    }
    return url.origin;
}

const config = {
    apiOrigin: serviceOrigin('IRIS_API_URL'),
    identityOrigin: serviceOrigin('IDP_API_URL'),
};
writeFileSync('deployment-config.js', `window.IRIS_DEPLOYMENT = ${JSON.stringify(config)};\n`);
