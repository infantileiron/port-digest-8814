-- 接驳配载批次：与 001_initial.sql 相同的导出风格，记录本特性新增表的实际 DDL。
-- ORM 首次启动自动建表；本文件作为结构留档，无在线迁移执行器。

CREATE TABLE public.load_batches (
    id integer NOT NULL,
    station character varying(30),
    business_day character varying(10),
    state character varying(20),
    plan json,
    fingerprint character varying(64),
    history json,
    revision integer,
    stale_note text,
    receipt_id integer,
    created_by character varying(100),
    created_at character varying(40),
    computed_at character varying(40),
    loaded_at character varying(40)
);

CREATE SEQUENCE public.load_batches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.load_batches_id_seq OWNED BY public.load_batches.id;

CREATE TABLE public.cargo_lots (
    id integer NOT NULL,
    batch_id integer,
    code character varying(60),
    volume double precision,
    note text
);

CREATE SEQUENCE public.cargo_lots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.cargo_lots_id_seq OWNED BY public.cargo_lots.id;

CREATE TABLE public.outbound_options (
    id integer NOT NULL,
    batch_id integer,
    code character varying(60),
    capacity double precision,
    min_transfer integer
);

CREATE SEQUENCE public.outbound_options_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.outbound_options_id_seq OWNED BY public.outbound_options.id;

ALTER TABLE ONLY public.load_batches ALTER COLUMN id SET DEFAULT nextval('public.load_batches_id_seq'::regclass);
ALTER TABLE ONLY public.cargo_lots ALTER COLUMN id SET DEFAULT nextval('public.cargo_lots_id_seq'::regclass);
ALTER TABLE ONLY public.outbound_options ALTER COLUMN id SET DEFAULT nextval('public.outbound_options_id_seq'::regclass);

ALTER TABLE ONLY public.load_batches
    ADD CONSTRAINT load_batches_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.cargo_lots
    ADD CONSTRAINT cargo_lots_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.outbound_options
    ADD CONSTRAINT outbound_options_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.load_batches
    ADD CONSTRAINT uq_loadbatch_station_day UNIQUE (station, business_day);

ALTER TABLE ONLY public.load_batches
    ADD CONSTRAINT load_batches_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(id);

ALTER TABLE ONLY public.cargo_lots
    ADD CONSTRAINT cargo_lots_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.load_batches(id);

ALTER TABLE ONLY public.outbound_options
    ADD CONSTRAINT outbound_options_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.load_batches(id);
