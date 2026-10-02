CREATE TABLE artifacts (
	id VARCHAR(64) NOT NULL, 
	source VARCHAR(60) NOT NULL, 
	url TEXT NOT NULL, 
	path TEXT NOT NULL, 
	downloaded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	period JSON NOT NULL, 
	bytes INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE runs (
	id VARCHAR(36) NOT NULL, 
	kind VARCHAR(40) NOT NULL, 
	parameters JSON NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	result JSON NOT NULL, 
	error TEXT, 
	PRIMARY KEY (id)
);

CREATE TABLE operations (
	id SERIAL NOT NULL, 
	country VARCHAR(2) NOT NULL, 
	regime VARCHAR(2) NOT NULL, 
	customs VARCHAR(3) NOT NULL, 
	year INTEGER NOT NULL, 
	declaration VARCHAR(8) NOT NULL, 
	series INTEGER NOT NULL, 
	numbered_on DATE NOT NULL, 
	importer_ruc VARCHAR(11), 
	importer TEXT, 
	supplier TEXT, 
	supplier_status VARCHAR(30) NOT NULL, 
	origin VARCHAR(3), 
	acquisition_country VARCHAR(3), 
	hs_code VARCHAR(10) NOT NULL, 
	description TEXT NOT NULL, 
	material VARCHAR(30) NOT NULL, 
	classification_reason TEXT NOT NULL, 
	needs_review BOOLEAN NOT NULL, 
	classification_locked BOOLEAN NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	quantity NUMERIC(22, 6), 
	unit VARCHAR(20), 
	net_kg NUMERIC(22, 6), 
	kg_method TEXT, 
	fob_usd NUMERIC(22, 6), 
	freight_usd NUMERIC(22, 6), 
	insurance_usd NUMERIC(22, 6), 
	cif_usd NUMERIC(22, 6), 
	usd_kg NUMERIC(22, 8), 
	search_text TEXT NOT NULL, 
	quality_flags JSON NOT NULL, 
	raw JSON NOT NULL, 
	record_hash VARCHAR(64) NOT NULL, 
	source_priority INTEGER NOT NULL, 
	source_modified_on DATE, 
	source_url TEXT NOT NULL, 
	artifact_id VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_operation UNIQUE (country, regime, customs, year, declaration, series), 
	FOREIGN KEY(artifact_id) REFERENCES artifacts (id)
);

CREATE TABLE alerts (
	id SERIAL NOT NULL, 
	fingerprint VARCHAR(100) NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	operation_id INTEGER NOT NULL, 
	title TEXT NOT NULL, 
	detail JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	read BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (fingerprint), 
	FOREIGN KEY(operation_id) REFERENCES operations (id)
);

CREATE TABLE reviews (
	id SERIAL NOT NULL, 
	operation_id INTEGER NOT NULL, 
	previous_material VARCHAR(30) NOT NULL, 
	material VARCHAR(30) NOT NULL, 
	note TEXT NOT NULL, 
	actor VARCHAR(100) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(operation_id) REFERENCES operations (id)
);

CREATE TABLE revisions (
	id SERIAL NOT NULL, 
	operation_id INTEGER NOT NULL, 
	artifact_id VARCHAR(64) NOT NULL, 
	record_hash VARCHAR(64) NOT NULL, 
	raw JSON NOT NULL, 
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_revision UNIQUE (operation_id, record_hash), 
	FOREIGN KEY(operation_id) REFERENCES operations (id), 
	FOREIGN KEY(artifact_id) REFERENCES artifacts (id)
);

CREATE INDEX ix_operations_hs_code ON operations (hs_code);

CREATE INDEX ix_operations_importer_date ON operations (importer_ruc, numbered_on);

CREATE INDEX ix_operations_importer_ruc ON operations (importer_ruc);

CREATE INDEX ix_operations_material ON operations (material);

CREATE INDEX ix_operations_numbered_on ON operations (numbered_on);

CREATE INDEX ix_operations_origin ON operations (origin);

CREATE INDEX ix_reviews_operation_id ON reviews (operation_id);

CREATE INDEX ix_revisions_operation_id ON revisions (operation_id);
