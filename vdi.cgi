#!/usr/bin/perl

# Список переменных:
# входящие переменные из веб: авторизация - $user, $password, $project
# переменные для БД: авторизация - $db, $login, $pass: коннект - $dbh, $str: значения из БД - $id
# переменные для временного хранения ответов: строки для авторизации в OS - $url, $auth, $ra, $req, $res, $json: массив с VM для VDI - @vmlist
# переменные для хранения значений keystone: строка авторизации - $token: идентификатор проекта: - $tenant: идентификатор VM - $vmid, идентификатор VM в БД - $id_vm: состояние VM - $stat
# :IP-адрес VM - $ip 
# Подпрограмма valid_ip предоставляющая IP адрес, $m и $y - опорные переменные, @valid_ip - опорный массив. 

use strict;
use DBI;
use CGI qw(param);
use LWP::UserAgent;
use Data::Dumper;
use JSON;

#[получение данных]

#парсинг полученой строки
my $user = param("user");
my $password = param("password");
my $project = param("project");

#выполнение запроса к keystone
my $auth = '{"auth":{"tenantName":"'.$project.'","passwordCredentials":{"username":"'.$user.'","password":"'.$password.'"}}}';
my $url = "http://controller:5000/v2.0/tokens";
my $ra = LWP::UserAgent->new;
my $req = HTTP::Request->new(POST=>$url);
    $req->content_type('application/json');
    $req->content($auth);
my $res = $ra->request($req);
my $json = $res->content;
$json = decode_json($json);
#Нормализация массива
my $token=$json->{'access'}{'token'}{'id'};
my $tenant=$json->{'access'}{'token'}{'tenant'}{'id'};


#четние файла конфигурации

open (CONFIG, "/etc/vdi/vdi.conf") or die "ERROR: Config file not found";
my %User_Preferences;
while (<CONFIG>) {
  chomp;               # Убрать перевод строки
  s/#.*//;             # Убрать комментарии
  s/^\s+//;            # Убрать начальные пропуски
  s/\s+$//;            # Убрать конечные пропуски
  next unless length;  # Что-нибудь осталось?
  my ($var, $value) = split(/\s*=\s*/, $_, 2);
  $User_Preferences{$var} = $value;
}
my $db = $User_Preferences{"db"};
my $login = $User_Preferences{"login"};
my $pass = $User_Preferences{"pass"};



#[обработка запроса]

#запрос в БД [vdi] 
my $dbh = DBI->connect("DBI:mysql:database=$db", $login, $pass) || die print "Can't connect";
$dbh->do('SET CHARACTER SET utf8');
my $str = $dbh->prepare("select id_vm from vdi_tbl where user='$user' and project='$project';");
$str->execute;
my $id = $str->fetchrow_array;
$str->finish;

#анализ значения из БД
my $id_vm;
my $vmid;
my $stat;
my $ip;
if (!$id){
#[если значение не существует]
#Выполнение запроса
$url = "http://controller:8774/v2/$tenant/servers";
$req = HTTP::Request->new(GET=>$url);
$req->content_type('application/json');
    $req->header('x-auth-token' => "$token");
    $req->content('');
$res = $ra->request($req);
$json = $res->content;
$json = decode_json($json);
#Нормализация массива
foreach ( @{$json->{'servers'}} )  {
#Выборка элемента из массива
    $vmid=$_->{'id'};
#Запрос в БД
    $str = $dbh->prepare("select id from vdi_tbl where id_vm='$vmid';");
    $str->execute;
#проверка наличия VM в БД
    $id_vm = $str->fetchrow_array;
#анализ значения из БД
	if (!$id_vm){
#протокол определения ip и статуса VM
			$url = "http://controller:8774/v2/$tenant/servers/$vmid";
			$req = HTTP::Request->new(GET=>$url);
			$req->content_type('application/json');
			    $req->header('x-auth-token' => "$token");
			    $req->content('');
			$res = $ra->request($req);
			$json = $res->content;
			$json = decode_json($json);

		        $stat=$json->{'server'}{'status'};
			    if ($stat eq "ACTIVE"){$ip = $json->{'server'}{'addresses'};
							valid_ip($ip, $vmid);
							reg_vm($vmid);
							    exit;}
				elsif ($stat eq "PAUSED"){$ip = $json->{'server'}{'addresses'};
#снятие с паузы
my $action = '{"unpause": null}';
$url = "http://controller:8774/v2/$tenant/servers/$vmid/action";
$ra = LWP::UserAgent->new;
$req = HTTP::Request->new(POST=>$url);
    $req->content_type('application/json');
    $req->header('x-auth-token' => $token);
    $req->content($action);
$res = $ra->request($req);
$json = $res->content;
valid_ip($ip, $vmid);
reg_vm($vmid);
exit;}
	    }else{
#подчистим хвосты, чтобы избежать ложного срабатывания при повторной итерации
$id_vm = undef;
  }
 }
}else{
#[если значение существует]
#протокол определения ip и статуса VM
			$url = "http://controller:8774/v2/$tenant/servers/$id";
			$req = HTTP::Request->new(GET=>$url);
			$req->content_type('application/json');
			    $req->header('x-auth-token' => "$token");
			    $req->content('');
			$res = $ra->request($req);
			$json = $res->content;
			$json = decode_json($json);
#нормализация массива
		        $stat=$json->{'server'}{'status'};
			    if ($stat eq "ACTIVE"){$ip = $json->{'server'}{'addresses'};
						valid_ip($ip, $id);
						    exit;}
				elsif ($stat eq "PAUSED"){$ip = $json->{'server'}{'addresses'};
#снятие с паузы
my $action = '{"unpause": null}';
$url = "http://controller:8774/v2/$tenant/servers/$id/action";
$ra = LWP::UserAgent->new;
$req = HTTP::Request->new(POST=>$url);
    $req->content_type('application/json');
    $req->header('x-auth-token' => $token);
    $req->content($action);
$res = $ra->request($req);
$json = $res->content;

valid_ip($ip, $id);
exit;}
				else {exit;}
}




#[ассоциирование пользователю VM в БД]
sub reg_vm{
my($m) = $_[0];
$str = $dbh->prepare(qq{insert into vdi_tbl(id_vm, project, user) values ('$m', '$project', '$user')});
$str->execute;
$str->finish;
$dbh->disconnect;
}


#[Подпрограмма, предоставляющая данные для подключения]
sub valid_ip{
my($m) = $_[0];
my($i) = $_[1];
my $y;
my @valid_ip;
while (@valid_ip = each $m){
    foreach (@{$valid_ip[1]}){
        $y=$_->{'addr'};
  }
#запрос novnc (веб-клиент)
my $auth_console = '{"os-getVNCConsole":{"type": "novnc"}}';
my $url_console = "http://controller:8774/v2/$tenant/servers/$i/action";
my $req_console = HTTP::Request->new(POST=>$url_console);
    $req_console->content_type('application/json');
    $req_console->header('x-auth-token' => $token);
    $req_console->content($auth_console);
my $res_console = $ra->request($req_console);
my $json_console = $res_console->content;
$json_console = decode_json($json_console);
my $connect = $json_console->{'console'}{'url'};

#формирование ответа
print "Content-type: text/html; charset=utf8 \n\n";
print '<HEAD></HEAD>';
print "<a href=\"$connect\">$y</a>";

 }
}