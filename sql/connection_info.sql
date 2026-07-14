SELECT
    @@SERVERNAME AS server_instance,
    DB_NAME() AS database_name,
    ORIGINAL_LOGIN() AS login_name,
    CONNECTIONPROPERTY('auth_scheme') AS auth_scheme,
    CONNECTIONPROPERTY('net_transport') AS net_transport,
    CONNECTIONPROPERTY('local_tcp_port') AS tcp_port;