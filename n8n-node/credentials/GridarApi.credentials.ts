import {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class GridarApi implements ICredentialType {
	name = 'gridarApi';
	displayName = 'Gridar API';
	documentationUrl = 'https://blog-dashboard-ebon.vercel.app/docs/api';

	properties: INodeProperties[] = [
		{
			displayName: 'API Token',
			name: 'apiToken',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			description:
				'Personal API token from Account -> API keys (looks like btb_xxxx). Generated at https://blog-dashboard-ebon.vercel.app/account/api-keys',
		},
		{
			displayName: 'API Base URL',
			name: 'apiBase',
			type: 'string',
			default: 'https://api.blog-dashboard.ca/api/v1',
			description: 'Override only if you self-host the Gridar backend.',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.apiToken}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.apiBase}}',
			url: '/me/',
			method: 'GET',
		},
	};
}
