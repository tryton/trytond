-------------------------------------------------------------------------
-- Modules Description
-------------------------------------------------------------------------

CREATE TABLE ir_model (
  id serial,
  model varchar DEFAULT ''::varchar NOT NULL,
  name varchar,
  info text,
  primary key(id)
);

CREATE TABLE ir_model_field (
  id serial,
  model int references ir_model on delete cascade,
  name varchar DEFAULT ''::varchar NOT NULL,
  relation varchar,
  field_description varchar,
  ttype varchar,
  group_name varchar,
  view_load boolean,
  relate boolean default False,
  help text,
  module varchar,
  primary key(id)
);


-------------------------------------------------------------------------
-- Actions
-------------------------------------------------------------------------
CREATE TABLE ir_ui_view (
	id serial NOT NULL,
	model varchar DEFAULT ''::varchar NOT NULL,
	"type" varchar DEFAULT 'form'::varchar NOT NULL,
	arch text NOT NULL,
	field_childs varchar,
	priority integer DEFAULT 5 NOT NULL,
	primary key(id)
);

CREATE TABLE ir_ui_menu (
	id serial NOT NULL,
	parent_id int references ir_ui_menu on delete set null,
	name varchar DEFAULT ''::varchar NOT NULL,
	icon varchar DEFAULT ''::varchar,
	primary key (id)
);



--------------------------------
-- Translation
--------------------------------

CREATE TABLE ir_translation (
    id serial NOT NULL,
    lang varchar,
    src text,
    name varchar NOT NULL,
    res_id integer DEFAULT 0,
    value text,
    "type" varchar,
    module varchar,
    fuzzy boolean default False,
    primary key(id)
);

CREATE TABLE ir_lang (
    id serial NOT NULL,
    name varchar NOT NULL,
    code varchar NOT NULL,
    translatable boolean default False,
    active boolean default True,
    direction varchar NOT NULL,
    primary key(id)
);

---------------------------------
-- Res user
---------------------------------

-- level:
--   0  RESTRICT TO USER
--   1  RESTRICT TO GROUP
--   2  PUBLIC

CREATE TABLE res_user (
    id serial NOT NULL,
    name varchar(64) not null,
    active boolean default True,
    login varchar(64) NOT NULL UNIQUE,
    password varchar(40) default null,
--  action_id int references ir_act_window on delete set null,
    action int,
    primary key(id)
);
alter table res_user add constraint res_user_login_uniq unique (login);

insert into res_user (id,login,password,name,action,active) values (0,'root',NULL,'Root',NULL,False);

CREATE TABLE res_group (
    id serial NOT NULL,
    name varchar NOT NULL,
    primary key(id)
);

CREATE TABLE res_group_user_rel (
	uid integer NOT NULL references res_user on delete cascade,
	gid integer NOT NULL references res_group on delete cascade
);

---------------------------------
-- Workflows
---------------------------------

create table wkf
(
    id serial,
    name varchar(64),
    osv varchar(64),
    on_create bool default False,
    primary key(id)
);

create table wkf_activity
(
    id serial,
    workflow int references wkf on delete cascade,
    subflow int references wkf on delete set null,
    split_mode varchar default 'XOR'::varchar,
    join_mode varchar default 'XOR'::varchar,
    kind varchar not null default 'dummy'::varchar,
    name varchar(64),
    signal_send varchar(32) default null,
    flow_start boolean default False,
    flow_stop boolean default False,
    action varchar default null,
    primary key(id)
);

create table wkf_transition
(
    id serial,
    act_from int references wkf_activity on delete cascade,
    act_to int references wkf_activity on delete cascade,
    condition varchar(128) default NULL,

    trigger_expr_id varchar(128) default NULL,

    signal varchar(64) default null,
    "group" int references res_group on delete set null,

    primary key(id)
);

create table wkf_instance
(
    id serial,
    workflow int references wkf on delete restrict,
    uid int default null,
    res_id int not null,
    res_type varchar(64) not null,
    state varchar(32) not null default 'active',
    primary key(id)
);

create table wkf_workitem
(
    id serial,
    activity int not null references wkf_activity on delete cascade,
    instance int not null references wkf_instance on delete cascade,
    subflow int references wkf_instance on delete cascade,
    state varchar(64) default 'blocked',
    primary key(id)
);

create table wkf_witm_trans
(
    trans_id int not null references wkf_transition on delete cascade,
    inst_id int not null references wkf_instance on delete cascade
);

---------------------------------
-- Modules
---------------------------------

CREATE TABLE ir_module_category (
    id serial NOT NULL,
    create_uid integer references res_user on delete set null,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    write_uid integer references res_user on delete set null,
    parent integer REFERENCES ir_module_category ON DELETE SET NULL,
    name character varying(128) NOT NULL,
    primary key(id)
);


CREATE TABLE ir_module_module (
    id serial NOT NULL,
    create_uid integer references res_user on delete set null,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    write_uid integer references res_user on delete set null,
    website character varying(256),
    name character varying(128) NOT NULL,
    author character varying(128),
    url character varying(128),
    state varchar,
    latest_version character varying(64),
    shortdesc character varying(256),
    category integer REFERENCES ir_module_category ON DELETE SET NULL,
    description text,
    primary key(id)
);
ALTER TABLE ir_module_module add constraint name_uniq unique (name);

CREATE TABLE ir_module_module_dependency (
    id serial NOT NULL,
    create_uid integer references res_user on delete set null,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    write_uid integer references res_user on delete set null,
    name character varying(128),
    version_pattern character varying(128) default NULL,
    module integer REFERENCES ir_module_module ON DELETE cascade,
    primary key(id)
);
