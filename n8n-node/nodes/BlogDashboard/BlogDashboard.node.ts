import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeConnectionType,
	NodeOperationError,
} from 'n8n-workflow';

export class BlogDashboard implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Blog Dashboard',
		name: 'blogDashboard',
		icon: 'file:blogDashboard.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
		description: 'Generate, audit and publish SEO articles via Blog Dashboard',
		defaults: {
			name: 'Blog Dashboard',
		},
		inputs: [NodeConnectionType.Main],
		outputs: [NodeConnectionType.Main],
		credentials: [
			{
				name: 'blogDashboardApi',
				required: true,
			},
		],
		requestDefaults: {
			baseURL: '={{$credentials.apiBase}}',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
			},
		},
		properties: [
			{
				displayName: 'Resource',
				name: 'resource',
				type: 'options',
				noDataExpression: true,
				options: [
					{ name: 'Article', value: 'article' },
					{ name: 'Audit', value: 'audit' },
					{ name: 'Brief', value: 'brief' },
					{ name: 'Keyword', value: 'keyword' },
					{ name: 'Site', value: 'site' },
				],
				default: 'article',
			},

			// ---------------- Article operations ----------------
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['article'] } },
				options: [
					{
						name: 'Generate',
						value: 'generate',
						description: 'Generate a new SEO article (consumes 1 quota)',
						action: 'Generate an article',
					},
					{
						name: 'Get',
						value: 'get',
						description: 'Get a single article by slug',
						action: 'Get an article',
					},
					{
						name: 'List',
						value: 'list',
						description: 'List articles on a site',
						action: 'List articles',
					},
				],
				default: 'generate',
			},

			// ---------------- Audit operations ----------------
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['audit'] } },
				options: [
					{
						name: 'Run Audit',
						value: 'run',
						description: 'Score raw content + get SEO suggestions',
						action: 'Run an SEO audit',
					},
				],
				default: 'run',
			},

			// ---------------- Brief operations ----------------
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['brief'] } },
				options: [
					{
						name: 'Build Brief',
						value: 'build',
						description: 'Build a content brief for a target keyword',
						action: 'Build a content brief',
					},
				],
				default: 'build',
			},

			// ---------------- Keyword operations ----------------
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['keyword'] } },
				options: [
					{
						name: 'List',
						value: 'list',
						description: 'List tracked keywords for a site',
						action: 'List keywords',
					},
					{
						name: 'Snapshot',
						value: 'snapshot',
						description: 'Trigger a fresh ranking snapshot',
						action: 'Snapshot keyword rankings',
					},
				],
				default: 'list',
			},

			// ---------------- Site operations ----------------
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['site'] } },
				options: [
					{
						name: 'List',
						value: 'list',
						description: 'List your sites',
						action: 'List sites',
					},
					{
						name: 'Weekly Digest',
						value: 'digest',
						description: 'Get weekly traffic + ranking digest',
						action: 'Get weekly digest',
					},
				],
				default: 'list',
			},

			// ---------------- Shared field: site_id ----------------
			{
				displayName: 'Site ID',
				name: 'siteId',
				type: 'number',
				typeOptions: { minValue: 1 },
				default: 0,
				required: true,
				displayOptions: {
					show: {
						resource: ['article', 'keyword'],
					},
				},
				description: 'Numeric ID of the site (use Site -> List to find it)',
			},
			{
				displayName: 'Site ID',
				name: 'siteId',
				type: 'number',
				typeOptions: { minValue: 1 },
				default: 0,
				required: true,
				displayOptions: {
					show: {
						resource: ['site'],
						operation: ['digest'],
					},
				},
			},

			// ---------------- Article -> Generate fields ----------------
			{
				displayName: 'Topic',
				name: 'topic',
				type: 'string',
				default: '',
				placeholder: 'meilleur CRM PME Quebec',
				displayOptions: {
					show: { resource: ['article'], operation: ['generate'] },
				},
				description: 'Topic to write about. Either Topic or Title is required.',
			},
			{
				displayName: 'Title',
				name: 'title',
				type: 'string',
				default: '',
				displayOptions: {
					show: { resource: ['article'], operation: ['generate'] },
				},
				description: 'Explicit title (overrides topic-based research)',
			},
			{
				displayName: 'Type',
				name: 'type',
				type: 'options',
				default: 'guide',
				displayOptions: {
					show: { resource: ['article'], operation: ['generate'] },
				},
				options: [
					{ name: 'Guide', value: 'guide' },
					{ name: 'News', value: 'news' },
					{ name: 'Tutorial', value: 'tutorial' },
					{ name: 'Comparison', value: 'comparison' },
					{ name: 'Review', value: 'review' },
					{ name: 'Story', value: 'story' },
					{ name: 'Local', value: 'local' },
				],
			},
			{
				displayName: 'Length',
				name: 'length',
				type: 'options',
				default: 'medium',
				displayOptions: {
					show: { resource: ['article'], operation: ['generate'] },
				},
				options: [
					{ name: 'Short (~600 words)', value: 'short' },
					{ name: 'Medium (~1200 words)', value: 'medium' },
					{ name: 'Long (~2000 words)', value: 'long' },
				],
			},
			{
				displayName: 'Language',
				name: 'language',
				type: 'options',
				default: 'fr',
				displayOptions: {
					show: { resource: ['article'], operation: ['generate'] },
				},
				options: [
					{ name: 'French', value: 'fr' },
					{ name: 'English', value: 'en' },
					{ name: 'Spanish', value: 'es' },
				],
			},
			{
				displayName: 'Keywords',
				name: 'keywords',
				type: 'string',
				default: '',
				displayOptions: {
					show: { resource: ['article'], operation: ['generate'] },
				},
				description: 'Comma-separated keywords to weave into the article',
			},

			// ---------------- Article -> Get/List fields ----------------
			{
				displayName: 'Slug',
				name: 'slug',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: { resource: ['article'], operation: ['get'] },
				},
			},
			{
				displayName: 'Status',
				name: 'status',
				type: 'options',
				default: '',
				displayOptions: {
					show: { resource: ['article'], operation: ['list'] },
				},
				options: [
					{ name: 'Any', value: '' },
					{ name: 'Draft', value: 'draft' },
					{ name: 'Published', value: 'published' },
					{ name: 'Archived', value: 'archived' },
				],
			},
			{
				displayName: 'Limit',
				name: 'limit',
				type: 'number',
				typeOptions: { minValue: 1, maxValue: 100 },
				default: 25,
				displayOptions: {
					show: { resource: ['article'], operation: ['list'] },
				},
			},

			// ---------------- Audit -> Run fields ----------------
			{
				displayName: 'Title',
				name: 'auditTitle',
				type: 'string',
				default: '',
				required: true,
				displayOptions: { show: { resource: ['audit'] } },
			},
			{
				displayName: 'Content',
				name: 'auditContent',
				type: 'string',
				typeOptions: { rows: 6 },
				default: '',
				required: true,
				displayOptions: { show: { resource: ['audit'] } },
				description: 'Raw HTML or Markdown content to score',
			},
			{
				displayName: 'Excerpt',
				name: 'auditExcerpt',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['audit'] } },
			},
			{
				displayName: 'Target Keyword',
				name: 'auditKeyword',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['audit'] } },
			},
			{
				displayName: 'Language',
				name: 'auditLanguage',
				type: 'options',
				default: 'fr',
				displayOptions: { show: { resource: ['audit'] } },
				options: [
					{ name: 'French', value: 'fr' },
					{ name: 'English', value: 'en' },
					{ name: 'Spanish', value: 'es' },
				],
			},

			// ---------------- Brief -> Build fields ----------------
			{
				displayName: 'Keyword',
				name: 'briefKeyword',
				type: 'string',
				default: '',
				required: true,
				displayOptions: { show: { resource: ['brief'] } },
			},
			{
				displayName: 'Language',
				name: 'briefLanguage',
				type: 'options',
				default: 'fr',
				displayOptions: { show: { resource: ['brief'] } },
				options: [
					{ name: 'French', value: 'fr' },
					{ name: 'English', value: 'en' },
					{ name: 'Spanish', value: 'es' },
				],
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		for (let i = 0; i < items.length; i++) {
			try {
				const resource = this.getNodeParameter('resource', i) as string;
				const operation = this.getNodeParameter('operation', i) as string;

				let endpoint = '';
				let method: 'GET' | 'POST' = 'GET';
				let body: Record<string, unknown> | undefined;
				const qs: Record<string, unknown> = {};

				if (resource === 'article') {
					const siteId = this.getNodeParameter('siteId', i) as number;

					if (operation === 'generate') {
						const topic = this.getNodeParameter('topic', i, '') as string;
						const title = this.getNodeParameter('title', i, '') as string;
						if (!topic && !title) {
							throw new NodeOperationError(
								this.getNode(),
								'Either "Topic" or "Title" must be provided for article.generate.',
								{ itemIndex: i },
							);
						}
						endpoint = `/sites/${siteId}/generate/`;
						method = 'POST';
						body = {
							...(topic ? { topic } : {}),
							...(title ? { title } : {}),
							type: this.getNodeParameter('type', i),
							length: this.getNodeParameter('length', i),
							language: this.getNodeParameter('language', i),
							keywords: this.getNodeParameter('keywords', i, ''),
						};
					} else if (operation === 'get') {
						const slug = this.getNodeParameter('slug', i) as string;
						endpoint = `/sites/${siteId}/articles/${encodeURIComponent(slug)}/`;
					} else if (operation === 'list') {
						endpoint = `/sites/${siteId}/articles/`;
						const status = this.getNodeParameter('status', i, '') as string;
						const limit = this.getNodeParameter('limit', i, 25) as number;
						if (status) qs.status = status;
						qs.limit = limit;
					}
				} else if (resource === 'audit') {
					endpoint = '/audit/';
					method = 'POST';
					body = {
						title: this.getNodeParameter('auditTitle', i),
						content: this.getNodeParameter('auditContent', i),
						excerpt: this.getNodeParameter('auditExcerpt', i, ''),
						keyword: this.getNodeParameter('auditKeyword', i, ''),
						language: this.getNodeParameter('auditLanguage', i),
					};
				} else if (resource === 'brief') {
					endpoint = '/brief/';
					method = 'POST';
					body = {
						keyword: this.getNodeParameter('briefKeyword', i),
						language: this.getNodeParameter('briefLanguage', i),
					};
				} else if (resource === 'keyword') {
					const siteId = this.getNodeParameter('siteId', i) as number;
					if (operation === 'list') {
						endpoint = `/sites/${siteId}/keywords/`;
					} else if (operation === 'snapshot') {
						endpoint = `/sites/${siteId}/keywords/snapshot/`;
						method = 'POST';
					}
				} else if (resource === 'site') {
					if (operation === 'list') {
						endpoint = '/sites/';
					} else if (operation === 'digest') {
						const siteId = this.getNodeParameter('siteId', i) as number;
						endpoint = `/sites/${siteId}/digest/weekly/`;
					}
				}

				const response = await this.helpers.httpRequestWithAuthentication.call(
					this,
					'blogDashboardApi',
					{
						method,
						url: endpoint,
						body,
						qs,
						json: true,
					},
				);

				returnData.push({ json: response, pairedItem: { item: i } });
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: { error: (error as Error).message },
						pairedItem: { item: i },
					});
					continue;
				}
				throw error;
			}
		}

		return [returnData];
	}
}
