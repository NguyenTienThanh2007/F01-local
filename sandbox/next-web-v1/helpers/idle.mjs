const seconds=Number(process.env.F01_LIFETIME_SECONDS);if(!Number.isInteger(seconds)||seconds<60||seconds>87600)throw Error('RUNTIME_LIMIT');setTimeout(()=>process.exit(0),seconds*1000);
