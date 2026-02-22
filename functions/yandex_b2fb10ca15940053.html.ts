export const onRequestGet = async () => {
  const body = `<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    </head>
    <body>Verification: b2fb10ca15940053</body>
</html>`;

  return new Response(body, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=UTF-8',
      'cache-control': 'public, max-age=300',
    },
  });
};
